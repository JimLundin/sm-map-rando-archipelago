lorom

; Archipelago multiworld basepatch for Super Metroid Map Rando (Map Rando v123+).
;
; All addresses below were chosen to avoid the space used by Map Rando's patches (patches/rom_map in the
; MapRandomizer repository). Addresses marked [MR] refer to code inside Map Rando's own patches and must be
; kept in sync with Map Rando.

macro a8()
	sep #$20
endmacro

macro a16()
	rep #$20
endmacro

macro i8()
	rep #$10
endmacro

macro ai8()
	sep #$30
endmacro

macro ai16()
	rep #$30
endmacro

macro i16()
	rep #$10
endmacro

!table_box = "table box_smmr.tbl"
!table_box_yellow = "table box_smmr.tbl"
!table_box_green = "table box_smmr.tbl"

; SRAM used for communication with the client ($70:263E-$70:2700 is free in Map Rando)
!SRAM_MW_ITEMS_RECV = $702640 ; current item RECV
!SRAM_MW_ITEMS_RECV_WCOUNT = $702644
!SRAM_SAVING = $702646

!SRAM_MW_ITEMS_SENT_RCOUNT = $702648
!SRAM_MW_ITEMS_SENT_WCOUNT = $70264A
!SRAM_MW_ITEMS_SENT = $70264C    ; current item SENT. [worldId, itemId, itemIndex] (need unique item index to prevent duping)

!SRAM_MW_SM = $70265E
!SRAM_MW_ROMTITLE = $702673
!SRAM_MW_SEEDINT = $70269E
!SRAM_MW_INITIALIZED = $7026A2

!SRAM_MW_CONFIG_ENABLED = $7026AE
!SRAM_MW_CONFIG_CUSTOM_SPRITE = $7026B0
!SRAM_MW_CONFIG_DEATHLINK = $7026B2
!SRAM_MW_CONFIG_REMOTE_ITEMS = $7026B4
!SRAM_MW_CONFIG_PLAYER_ID = $7026B6

; Item ids, see mr_itemextras.asm
!mr_item_nothing = $0016
!mr_item_spark_booster = $0017
!mr_item_blue_booster = $0018
!mr_item_count = $0019

; [MR] Map Rando PLM data (walljump_plm.asm, split_speed_plm.asm)
!mr_walljump_gfx_entry = $F00E
!mr_walljump_pickup = $F031
!mr_spark_booster_gfx_entry = $F0FC
!mr_spark_booster_pickup = $F11F
!mr_blue_booster_gfx_entry = $F1A6
!mr_blue_booster_pickup = $F1C9

; [MR] Map Rando saveload.asm: "JSL set_marker_colors" at the end of LoadGame
!mr_load_hook = $81F0BF
!mr_set_marker_colors = $8FEA5C

; Free space used by this patch
!mr_bank80_start = $80E700
!mr_bank80_end = $80F000
!mr_bank83_playertable_start = $83BC40
!mr_bank83_itemtable_start = $83CA80
!mr_bank83_end = $83E000
!mr_bank84_block1_start = $84F300
!mr_bank84_block1_end = $84F380
!mr_bank84_block2_start = $84FB47
!mr_bank84_block2_end = $84FC00
!mr_bank85_message_start = $85C410
!mr_bank85_end = $85F000
!mr_offworld_gfx_start = $89C000

org $808000				; Disable copy protection screen
	db $ff

; Config flags
incsrc ../../common/config.asm

; Add code to the main code bank
org !mr_bank80_start
incsrc mr_multiworld.asm
incsrc mr_itemextras.asm
assert pc() <= !mr_bank80_end

incsrc mr_items.asm

org !mr_bank83_playertable_start
incsrc ../../common/playertable.asm
assert pc() <= !mr_bank83_itemtable_start

org !mr_bank83_itemtable_start
incsrc ../../common/itemtable.asm
assert pc() <= !mr_bank83_end
