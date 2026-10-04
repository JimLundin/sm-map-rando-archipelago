; Archipelago item PLMs for Map Rando (v123+).
;
; Based on common/items.asm, but restructured to fit in the small amount of free space that Map Rando
; leaves in bank $84: the unused ammo loop sequences and the "load rando item" indirection were removed,
; and the item -> graphics mapping is shared with bank $80 code (mr_location_gfx_index).
;
; Every item location in an Archipelago Map Rando ROM uses one of these 3 PLMs. The patcher computes
; the PLM ids from the symbols archipelago_*_item_plm.

!IBranchItem = $887C
!ISetItem = $8899
!ISetGoto = $8A24
!ISetPreInstructionCode = $86C1
!IDrawCustom1 = $E04F
!IDrawCustom2 = $E067
!IGoto = $8724
!IKill = $86BC
!IJSR = $8A2E
!ISetCounter8 = $874E
!IGotoDecrement = $873F

!Click = $37			;Sound when selecting a HUD item

; ---------------------------------------------------------------------------------------------------
org !mr_bank84_block1_start

archipelago_visible_item_plm:
    dw i_visible_item_setup, p_visible_item
archipelago_chozo_item_plm:
    dw i_visible_item_setup, p_chozo_item
archipelago_hidden_item_plm:
    dw i_hidden_item_setup,  p_hidden_item

; PLM graphics entries for off-world items (arguments for the vanilla "load item PLM GFX" instruction $84:8764)
plm_graphics_entry_offworld_progression_item:
    dw offworld_graphics_data_progression_item
prog_item_eight_palette_indices: ; symbol provided for AP patcher to overwrite these 8 bytes:
    db $00, $00, $00, $00, $00, $00, $00, $00
plm_graphics_entry_offworld_item:
    dw offworld_graphics_data_item
nonprog_item_eight_palette_indices: ; symbol provided for AP patcher to overwrite these 8 bytes:
    db $00, $00, $00, $00, $00, $00, $00, $00

p_visible_item:
    dw i_load_custom_graphics
    dw !IBranchItem, .end
    dw !ISetGoto, .trigger
    dw !ISetPreInstructionCode, $df89
.loop
    dw !IBranchItem, .end
    dw !IDrawCustom1
    dw !IDrawCustom2
    dw !IGoto, .loop
.trigger
    dw !ISetItem
    dw SOUNDFX_84 : db !Click
    dw i_live_pickup
.end
    dw !IGoto, $dfa9

p_chozo_item:
    dw i_load_custom_graphics
    dw !IBranchItem, .end
    dw !IJSR, $dfaf
    dw !IJSR, $dfc7
    dw !ISetGoto, .trigger
    dw !ISetPreInstructionCode, $df89
    dw !ISetCounter8 : db $16
.loop
    dw !IBranchItem, .end
    dw !IDrawCustom1
    dw !IDrawCustom2
    dw !IGoto, .loop
.trigger
    dw !ISetItem
    dw SOUNDFX_84 : db !Click
    dw i_live_pickup
.end
    dw $0001, $a2b5
    dw !IKill

assert pc() <= !mr_bank84_block1_end

; ---------------------------------------------------------------------------------------------------
org !mr_bank84_block2_start

p_hidden_item:
    dw i_load_custom_graphics
.loop2
    dw !IJSR, $e007
    dw !IBranchItem, .end
    dw !ISetGoto, .trigger
    dw !ISetPreInstructionCode, $df89
    dw !ISetCounter8 : db $16
.loop
    dw !IBranchItem, .end
    dw !IDrawCustom1
    dw !IDrawCustom2
    dw !IGotoDecrement, .loop
    dw !IJSR, $e020
    dw !IGoto, .loop2
.trigger
    dw !ISetItem
    dw SOUNDFX_84 : db !Click
    dw i_live_pickup
.end
    dw !IJSR, $e032
    dw !IGoto, .loop2

; PLM instruction: queue sound effect (library 1) given by the following byte.
; (Same as SOUNDFX in Map Rando's itemsounds.asm, which is only present when item fanfares are off.)
SOUNDFX_84:
    lda #$0002
    sta $05D7
    lda $0000,y
    iny
    jsl $809049
    rts

; PLM instruction: load the graphics of the item at this location
i_load_custom_graphics:
    phy : phx
    lda $1dc7, x                   ; Load PLM room argument (tells us which of the 100 items this is)
    jsl mr_location_gfx_index
    asl
    tax
    lda.l sm_item_graphics, x
    tay ; Y = pointer to 10-byte graphics entry to load (implied bank $84)
    plx ; X = PLM index again
    jsr $8764               ; Jump to original PLM graphics loading routine ($84:8764)
    ply
    rts

i_visible_item_setup:
    jsl i_item_setup_shared
    jmp $ee64 ; generic visible item setup

i_hidden_item_setup:
    jsl i_item_setup_shared
    jmp $ee8e

; PLM instruction: pick up the item
i_live_pickup:
    jsl i_live_pickup_multiworld
    rts

; X = byte offset into sm_item_plm_pickup_sequence_pointers of item to pick up
; (clobbers Y)
perform_item_pickup:
    phx
    phb
    phk : plb ; DB = $84
    ; sm_item_plm_pickup_sequence_pointers[entry]: ROM data pointer
    ; in turn...                                   ROM data pointer -> function pointer, function args
    ; (ROM data pointer's implied bank is bank $84)
    lda.l sm_item_plm_pickup_sequence_pointers, x
    tax ; X = ROM data pointer
    tay
    iny : iny ; Y = points to function args (pointer X + 2 bytes)
    jsr ($0000,x) ; X is not a function pointer but it points to one
    plb
    plx
    rtl

; function pointer data usable for 'picking up' other players' items (which to SM is just a message box)
plm_sequence_generic_item_0_bitmask:
    ; $84:88F3 = generic item pickup function, parameters:
    ;   #$0000 = do not actually pick up an item (this gets harmlessly OR'ed into samus's equipment)
    ;   #$19 = reserve tank's message box id (will be overriden)
    dw $88F3, $0000 : db $19

assert pc() <= !mr_bank84_block2_end

; ---------------------------------------------------------------------------------------------------
pushpc
org !mr_offworld_gfx_start
offworld_graphics_data_progression_item:
org !mr_offworld_gfx_start+$100
offworld_graphics_data_item:
; the randomizer's patcher will write the actual graphics here
pullpc
