# Super Metroid Map Rando Setup Guide

## Required Software

- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.6 or newer. Make sure to install the
  `SNI Client`.
- The `sm_map_rando.apworld` file.
- Hardware or software capable of loading and playing SNES ROM files, and connecting to SNI:
    - snes9x-rr ([snes9x rr](https://github.com/gocha/snes9x-rr/releases)), BizHawk
      ([TASVideos](https://tasvideos.org/BizHawk)) or RetroArch 1.10.1 or newer
      ([RetroArch Website](https://retroarch.com?page=platforms)), or
    - an SD2SNES or FXPak Pro ([FXPak Pro Store Page](https://krikzz.com/store/home/54-fxpak-pro.html)), or other
      compatible hardware.
- Your legally obtained Super Metroid ROM file, probably named `Super Metroid (Japan, USA).sfc` (headered and unheadered
  ROMs both work).

## Installation

1. Double click `sm_map_rando.apworld` (or copy it into the `custom_worlds` folder of your Archipelago installation).
2. The first time a Super Metroid Map Rando patch is opened, you will be asked to locate your Super Metroid ROM file.
3. If you are using an emulator, assign it as the default program for `.sfc` files, so that it opens automatically.

The world includes the native Map Rando randomizer for Windows (x86-64) and Linux (x86-64). On first use it is
extracted to the Archipelago cache directory. For other platforms (e.g. macOS), see "Building the native module" below.

## Create a Config (.yaml) File

### What is a config file and why do I need one?

See the guide on setting up a basic YAML at the Archipelago setup
guide: [Basic Multiworld Setup Guide](/tutorial/Archipelago/setup/en)

### Where do I get a config file?

The Player Options page on the website allows you to configure your options and export a config file from
them: [Super Metroid Map Rando Player Options Page](/games/Super%20Metroid%20Map%20Rando/player-options). You can also
use the "Generate Template Options" command of the Archipelago Launcher.

The options mirror the settings of [maprando.com](https://maprando.com): pick a `settings_preset` and category presets
(`skill_assumptions_preset`, `item_progression_preset`, `quality_of_life_preset`, `objectives_preset`,
`doors_preset`), then change any individual setting. Individual settings default to `preset`, which keeps the value of
the selected preset. For example:

```yaml
Super Metroid Map Rando:
  settings_preset: default
  skill_assumptions_preset: hard
  quality_of_life_preset: high
  map_layout: wild
  start_location: randomized
  wall_jump: collectible
  shinespark_tiles: 15
  tech_enabled: [canMockball]
  samus_sprite: samus_dread
```

You can also design your settings on maprando.com and paste the settings JSON into `map_rando_settings`.

## Joining a MultiWorld Game

### Obtain your patch file and create your ROM

When you join a multiworld game, you will be asked to provide your config file to whoever is hosting. Once that is done,
the host will provide you with either a link to download your patch file, or with a zip file containing everyone's patch
files. Your patch file should have a `.apsmmr` extension.

Double click the patch file: this launches the SNI client and creates your ROM in the same place as the patch file.
The first time, creating the ROM downloads Map Rando's Mosaic tile patches (8 MB), and your Samus sprite if it isn't
the default one; they are cached.

### Connect to the client

#### With an emulator

When the client launches, SNI should start automatically in the background. If this is the first time, you may be
prompted to allow it to communicate through the Windows Firewall.

##### snes9x-rr

1. Load your ROM file if it hasn't already been loaded.
2. Click on the File menu and hover on **Lua Scripting**
3. Click on **New Lua Script Window...**
4. In the new window, click **Browse...**
5. Select the connector lua file included with your client
    - Look in the Archipelago folder for `/SNI/lua/Connector.lua`.

##### BizHawk

1. Ensure you have the BSNES core loaded. In the menu bar, go to `Config > Cores > SNES` and choose `BSNES`.
2. Load your ROM file if it hasn't already been loaded. If you changed your core preference after loading the ROM,
   reload it (default hotkey: Ctrl+R).
3. Drag+drop the `Connector.lua` file included with your client onto the main EmuHawk window.
    - Look in the Archipelago folder for `/SNI/lua/Connector.lua`.
    - You could instead open the Lua Console manually, click `Script` 〉 `Open Script`, and navigate to `Connector.lua`
      with the file picker.

##### RetroArch 1.10.1 or newer

You only have to do these steps once. Note, RetroArch 1.9.x will not work as it is older than 1.10.1.

1. Enter the RetroArch main menu screen.
2. Go to Settings --> User Interface. Set "Show Advanced Settings" to ON.
3. Go to Settings --> Network. Set "Network Commands" to ON. (It is found below Request Device 16.) Leave the default
   Network Command Port at 55355.
4. Go to Main Menu --> Online Updater --> Core Downloader. Scroll down and select "Nintendo - SNES / SFC (bsnes-mercury
   Performance)".

When loading a ROM, be sure to select a **bsnes-mercury** core. These are the only cores that allow external tools to
read ROM data.

#### With hardware

This guide assumes you have downloaded the correct firmware for your device. If you have not done so already, please do
this now. SD2SNES and FXPak Pro users may download the appropriate firmware on the SD2SNES releases page. SD2SNES
releases page: [SD2SNES Releases Page](https://github.com/RedGuyyyy/sd2snes/releases)

Other hardware may find helpful information on the usb2snes platforms
page: [usb2snes Supported Platforms Page](http://usb2snes.com/#supported-platforms)

1. Close your emulator, which may have auto-launched.
2. Power on your device and load the ROM.

### Connect to the Archipelago Server

The patch file which launched your client should have automatically connected you to the AP Server. There are a few
reasons this may not happen, however, including if the game is hosted on the website but was generated elsewhere. If
the client window shows "Server Status: Not Connected", simply ask the host for the address of the server, and copy/paste
it into the "Server" input field then press enter.

The client will attempt to reconnect to the new server address, and should momentarily show "Server Status: Connected".

### Play the game

When the client shows both SNES Device and Server as connected, you're ready to begin playing. Congratulations on
successfully joining a multiworld game!

## Hosting a MultiWorld game

The recommended way to host a game is to use our hosting service. The process is relatively simple:

1. Collect config files from your players.
2. Create a zip file containing your players' config files.
3. Upload that zip file to the Generate page above.
    - Generate page: [WebHost Seed Generation Page](/generate)
4. Wait a moment while the seed is generated.
5. When the seed is generated, you will be redirected to a "Seed Info" page.
6. Click "Create New Room". This will take you to the server page. Provide the link to this page to your players, so
   they may download their patch files from there.
7. Note that a link to a MultiWorld Tracker is at the top of the room page. The tracker shows the progress of all
   players in the game. Any observers may also be given the link to this page.
8. Once all players have joined, you may begin playing.

## Building the native module

The randomizer is Rust code (the upstream Map Rando crates plus thin Python bindings, `pysmmaprando`). To build it for
another platform, install Rust and [maturin](https://www.maturin.rs/), then in the `rust/pysmmaprando` directory of the
Map Rando sources used by this world run:

```
maturin build --release
pip install target/wheels/pysmmaprando-*.whl
```

An installed `pysmmaprando` of the right version is used in preference to the bundled ones.
