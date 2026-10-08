//! The world apart from the item placement, and the logic over it.
//!
//! A `World` is everything Map Rando decides before it places items: the map, the locked doors, the objectives, the
//! start location and its hub, and what follows from them alone (escape time, Toilet intersections). Archipelago
//! places the items; `reach` answers which item locations a set of collected items makes reachable, as one step of
//! Map Rando's own placement loop does (`Randomizer::randomize`), and `randomization` puts a world and a placement
//! together for `make_rom`.

use maprando::randomize::{
    DoorState, EssentialSpoilerData, FlagLocationState, ForeignItem, ItemLocationState, LockedDoor,
    Randomization, RandomizationState, Randomizer, SaveLocationState, TraverserPair,
};
use maprando::settings::{Objective, SaveAnimals};
use maprando::traverse::Traverser;
use maprando_game::{
    Capacity, GameData, HubLocation, Item, Map, Requirement, RoomGeometryRoomIdx, StartLocation, VertexKey,
};
use maprando_logic::{GlobalState, Inventory, LocalState};
use rand::{Rng, SeedableRng};
use serde_derive::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Clone)]
pub struct World {
    pub map: Map,
    pub locked_doors: Vec<LockedDoor>,
    pub objectives: Vec<Objective>,
    pub start_location: StartLocation,
    pub hub: (usize, usize), // (room id, node id): where the logic starts, and must be able to return to
    pub save_animals: SaveAnimals,
    pub escape_time_seconds: f32,
    pub toilet_intersections: Vec<RoomGeometryRoomIdx>,
    pub seed: usize,
    pub display_seed: usize,
}

/// What a set of collected items makes reachable.
#[derive(Serialize)]
pub struct Reach {
    /// Item locations Samus can reach and come back from (to the hub): Map Rando collects only these.
    pub locations: Vec<usize>,
    /// Item locations she can reach but not (yet) come back from.
    pub one_way: Vec<usize>,
    /// Flags (bosses, events, objectives) that are set.
    pub flags: Vec<String>,
    /// Mother Brain can be defeated.
    pub beatable: bool,
}

pub fn hub_location(randomizer: &Randomizer, hub: (usize, usize)) -> HubLocation {
    HubLocation { room_id: hub.0, node_id: hub.1, vertex_id: vertex(randomizer, hub) }
}

fn vertex(randomizer: &Randomizer, (room_id, node_id): (usize, usize)) -> usize {
    randomizer.game_data.vertex_isv.index_by_key[&VertexKey { room_id, node_id, obstacle_mask: 0, actions: vec![] }]
}

fn collect(randomizer: &Randomizer, global: &mut GlobalState, item: Item) {
    let p = &randomizer.settings.item_progression_settings;
    global.collect(
        item,
        randomizer.game_data,
        p.ammo_collect_fraction,
        p.missile_size,
        p.super_size,
        p.powerbomb_size,
        p.etank_size,
        p.reserve_size,
        &randomizer.difficulty_tiers[0].tech,
    );
}

/// The item pool's capacities (Map Rando's private `Randomizer::get_pool_inventory`).
fn pool_inventory(randomizer: &Randomizer) -> Inventory {
    let settings = &randomizer.settings.item_progression_settings;
    let remaining = &randomizer.initial_items_remaining;
    let acf = settings.ammo_collect_fraction;
    let packs = |item: Item| remaining[item as usize];
    Inventory {
        items: remaining.iter().map(|&x| x > 0).collect(),
        max_energy: (99 + packs(Item::ETank) * 100) as Capacity,
        max_reserves: (packs(Item::ReserveTank) * 100) as Capacity,
        max_missiles: (acf * packs(Item::Missile) as f32).round() as Capacity * settings.missile_size as Capacity,
        max_supers: (acf * packs(Item::Super) as f32).round() as Capacity * settings.super_size as Capacity,
        max_power_bombs: (acf * packs(Item::PowerBomb) as f32).round() as Capacity
            * settings.powerbomb_size as Capacity,
        collectible_missile_packs: packs(Item::Missile) as Capacity,
        collectible_super_packs: packs(Item::Super) as Capacity,
        collectible_power_bomb_packs: packs(Item::PowerBomb) as Capacity,
        collectible_reserve_tanks: packs(Item::ReserveTank) as Capacity,
    }
}

/// The global state with the starting items and `collected` (Map Rando's private `Randomizer::get_initial_states`).
pub fn global_state(randomizer: &Randomizer, collected: &[(Item, usize)]) -> GlobalState {
    let game_data = randomizer.game_data;
    let items = vec![false; game_data.item_isv.keys.len()];
    let weapon_mask = game_data.get_weapon_mask(&items, &randomizer.difficulty_tiers[0].tech);
    let mut flags = vec![false; game_data.flag_isv.keys.len()];
    flags[game_data.flag_isv.index_by_key["f_TourianOpen"]] = true;
    let mut global = GlobalState {
        inventory: Inventory {
            items,
            max_energy: 99,
            max_reserves: 0,
            max_missiles: 0,
            max_supers: 0,
            max_power_bombs: 0,
            collectible_missile_packs: 0,
            collectible_super_packs: 0,
            collectible_power_bomb_packs: 0,
            collectible_reserve_tanks: 0,
        },
        pool_inventory: pool_inventory(randomizer),
        flags,
        doors_unlocked: vec![false; randomizer.locked_door_data.locked_doors.len()],
        weapon_mask,
    };
    let starting = randomizer.starting_items.iter().map(|x| (x.item, x.count));
    for (item, count) in starting.chain(collected.iter().copied()) {
        for _ in 0..count {
            collect(randomizer, &mut global, item);
        }
    }
    global
}

/// What `collected` (on top of the starting items) makes reachable from the hub: a traversal, then Map Rando's
/// fixed point of flags and locked doors (from `Randomizer::step`), traversing again until nothing changes.
pub fn reach(randomizer: &Randomizer, world: &World, collected: &[(Item, usize)]) -> Reach {
    reach_chain(randomizer, world, &[collected.to_vec()]).pop().unwrap()
}

/// `reach` for each of `inventories`, each with the traversal of the one before it continued, as Map Rando's
/// placement loop continues its traversal from step to step (each inventory must contain the one before it).
pub fn reach_chain(randomizer: &Randomizer, world: &World, inventories: &[Vec<(Item, usize)>]) -> Vec<Reach> {
    let game_data = randomizer.game_data;
    let negated = negated_flags(game_data);
    let global = global_state(randomizer, &inventories[0]);
    let local = LocalState::empty();
    let num_vertices = game_data.vertex_isv.keys.len();
    let mut traversers = TraverserPair {
        forward: Traverser::new(num_vertices, false, local, &global),
        reverse: Traverser::new(num_vertices, true, local, &global),
    };
    let hub = hub_location(randomizer, world.hub);
    traversers.forward.add_origin(local, &global.inventory, hub.vertex_id);
    traversers.forward.finish_step(1);
    traversers.reverse.add_origin(LocalState::full(true), &global.inventory, hub.vertex_id);
    traversers.reverse.finish_step(1);
    let mut state = RandomizationState {
        step_num: 1,
        start_location: world.start_location.clone(),
        hub_location: hub,
        item_precedence: vec![],
        save_location_state: vec![SaveLocationState { bireachable_traversal: None }; game_data.save_locations.len()],
        item_location_state: vec![
            ItemLocationState {
                placed_item: None,
                placed_tier: None,
                collected: false,
                reachable_traversal: None,
                bireachable_traversal: None,
                bireachable_vertex_id: None,
                difficulty_tier: None,
            };
            game_data.item_locations.len()
        ],
        flag_location_state: vec![
            FlagLocationState {
                reachable_traversal: None,
                reachable_vertex_id: None,
                bireachable_traversal: None,
                bireachable_vertex_id: None,
            };
            game_data.flag_ids.len()
        ],
        door_state: vec![
            DoorState { bireachable_traversal: None, bireachable_vertex_id: None };
            randomizer.locked_door_data.locked_doors.len()
        ],
        items_remaining: randomizer.initial_items_remaining.clone(),
        global_state: global,
        starting_local_state: local,
        last_key_areas: vec![],
    };
    let mut results = vec![];
    for (k, collected) in inventories.iter().enumerate() {
        if k > 0 {
            let next = global_state(randomizer, collected);
            state.global_state.inventory = next.inventory;
            state.global_state.weapon_mask = next.weapon_mask;
            state.step_num += 1;
        }
        randomizer.update_reachability(&mut state, &mut traversers);
        // Map Rando's fixed point of flags and doors (Randomizer::step), staged: some strats need a flag *not* to be
        // set (e.g. Wrecked Ship before Phantoon), so the flags they negate are set last, one at a time, each after
        // everything else settled. Location results stick (as in Map Rando), so each stage is a play order: what's
        // reachable before Phantoon, then after.
        loop {
            settle(randomizer, &mut state, &mut traversers, &negated);
            let next = game_data.flag_ids.iter().enumerate().find(|&(i, &flag_id)| {
                negated[flag_id] && !state.global_state.flags[flag_id] && flag_reached(randomizer, &state, i, flag_id)
            });
            let Some((_, &flag_id)) = next else { break };
            state.global_state.flags[flag_id] = true;
            randomizer.update_reachability(&mut state, &mut traversers);
        }
        let locations = state.item_location_state.iter().enumerate();
        results.push(Reach {
            locations: locations.clone().filter(|(_, x)| x.bireachable_traversal.is_some()).map(|(i, _)| i).collect(),
            one_way: locations
                .filter(|(_, x)| x.bireachable_traversal.is_none() && x.reachable_traversal.is_some())
                .map(|(i, _)| i)
                .collect(),
            flags: (0..game_data.flag_isv.keys.len())
                .filter(|&f| state.global_state.flags[f])
                .map(|f| game_data.flag_isv.keys[f].clone())
                .collect(),
            beatable: state.global_state.flags[game_data.mother_brain_defeated_flag_id],
        });
    }
    results
}

/// The flags some requirement needs not to be set (`{"not": flag}` in sm-json-data).
fn negated_flags(game_data: &GameData) -> Vec<bool> {
    fn walk(requirement: &Requirement, out: &mut Vec<bool>) {
        match requirement {
            Requirement::NotFlag(flag_id) => out[*flag_id] = true,
            Requirement::And(requirements) | Requirement::Or(requirements) => {
                requirements.iter().for_each(|r| walk(r, out))
            }
            Requirement::Farm { requirement, .. } => walk(requirement, out),
            Requirement::UnlockDoor {
                requirement_red, requirement_green, requirement_yellow, requirement_charge, ..
            } => {
                for r in [requirement_red, requirement_green, requirement_yellow, requirement_charge] {
                    walk(r, out);
                }
            }
            _ => {}
        }
    }
    let mut out = vec![false; game_data.flag_isv.keys.len()];
    for link in &game_data.links {
        walk(&link.requirement, &mut out);
    }
    out
}

/// Whether flag location `i` (flag `flag_id`) is reached: bireachable, or for Mother Brain one-way reachable, as in
/// Map Rando.
fn flag_reached(randomizer: &Randomizer, state: &RandomizationState, i: usize, flag_id: usize) -> bool {
    let flag_state = &state.flag_location_state[i];
    flag_state.bireachable_traversal.is_some()
        || (flag_id == randomizer.game_data.mother_brain_defeated_flag_id && flag_state.reachable_traversal.is_some())
}

/// Sets the reached flags (except `deferred` ones) and unlocks the reached locked doors, traversing again until
/// nothing changes.
fn settle(randomizer: &Randomizer, state: &mut RandomizationState, traversers: &mut TraverserPair, deferred: &[bool]) {
    let game_data = randomizer.game_data;
    loop {
        let mut any_update = false;
        for (i, &flag_id) in game_data.flag_ids.iter().enumerate() {
            if !deferred[flag_id] && !state.global_state.flags[flag_id] && flag_reached(randomizer, state, i, flag_id) {
                state.global_state.flags[flag_id] = true;
                any_update = true;
            }
        }
        for i in 0..randomizer.locked_door_data.locked_doors.len() {
            if state.door_state[i].bireachable_traversal.is_some() && !state.global_state.doors_unlocked[i] {
                state.global_state.doors_unlocked[i] = true;
                any_update = true;
            }
        }
        if !any_update {
            return;
        }
        randomizer.update_reachability(state, traversers);
    }
}

/// The item pool Map Rando would place, by item: everything `reach` can be given.
pub fn pool(randomizer: &Randomizer) -> Vec<(Item, usize)> {
    (0..randomizer.initial_items_remaining.len())
        .filter(|&i| randomizer.initial_items_remaining[i] > 0)
        .map(|i| (Item::try_from(i).unwrap(), randomizer.initial_items_remaining[i]))
        .collect()
}

/// A world that Archipelago can place items in: something is reachable at the start, and with the whole pool the
/// game is beatable (and Phantoon defeated, unless the map is Small: Map Rando's own checks after placing items).
pub fn check(randomizer: &Randomizer, world: &World) -> Result<(), String> {
    if reach(randomizer, world, &[]).locations.is_empty() {
        return Err("no item location is reachable at the start".into());
    }
    let full = reach(randomizer, world, &pool(randomizer));
    if !full.beatable {
        return Err("not beatable with every item".into());
    }
    if randomizer.settings.map_layout != "Small" && !full.flags.iter().any(|f| f == "f_DefeatedPhantoon") {
        return Err("Phantoon can't be defeated with every item".into());
    }
    Ok(())
}

/// A deterministic seed name (Map Rando's `get_seed_name` mixes in the time): 9 characters without vowels.
fn seed_name(seed: usize) -> String {
    let mut rng_seed = [0u8; 32];
    rng_seed[..8].copy_from_slice(&seed.to_le_bytes());
    let mut rng = rand::rngs::StdRng::from_seed(rng_seed);
    let alphabet = "256789BCDFGHJKLMNPQRSTVWXYZbcdfghjkmnpqrstvwxyz".as_bytes();
    (0..9).map(|_| alphabet[rng.gen_range(0..alphabet.len())] as char).collect()
}

/// The world with an item placement, as `make_rom` takes it.
pub fn randomization(
    world: World,
    item_placement: Vec<Item>,
    foreign_items: Vec<ForeignItem>,
) -> Randomization {
    Randomization {
        objectives: world.objectives,
        save_animals: world.save_animals,
        map: world.map,
        toilet_intersections: world.toilet_intersections,
        locked_doors: world.locked_doors,
        item_placement,
        foreign_items,
        start_location: world.start_location,
        escape_time_seconds: world.escape_time_seconds,
        essential_spoiler_data: EssentialSpoilerData { item_spoiler_info: vec![] },
        seed: world.seed,
        display_seed: world.display_seed,
        seed_name: seed_name(world.seed),
    }
}
