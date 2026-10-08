; Super Metroid Map Rando multiworld patch: receiving items.
;
; Sending needs no code here: items for other worlds are Map Rando foreign items (ADR 0005), whose pickup sets the
; vanilla item-collected bit like any item, and the client reads those bits.
;
; Receiving: the client puts one item in the mailbox (abi.toml [wram]). During main gameplay, the tick spawns that
; item's own Map Rando item PLM on Samus, with a negative room argument (no collected bit), and triggers it once it
; waits to be touched. The pickup is then the game's own: equipment, ammo, fanfare and message box.
;
; Assembled by tools/build_mw.py, with the defines generated from abi.toml in build/abi.asm.

lorom
incsrc "build/abi.asm"

!plm_handler = $8485B4
!plm_handler_rtl = $85D9            ; the RTL that ends the PLM handler, in bank $84
!room_width_blocks = $07A5
!samus_x = $0AF6
!samus_y = $0AFA
!plm_ids = $1C37
!plm_block_indices = $1C87
!plm_pre_instructions = $1CD7
!plm_instruction_lists = $1D27
!plm_room_arguments = $1DC7
!plm_1d77 = $1D77                  ; cleared on spawn
!plm_timers = $7EDE1C
!plm_link_instructions = $7EDEBC
!plm_draw_instructions = $7EDE6C
!plm_item_gfx_indices = $7EDF0C
!wait_for_trigger = $DF89          ; item PLM pre-instruction: go to link instruction when touched

org !rom_hook_plm_handler
    jsl mw_tick

org !rom_code
mw_tick:
    php
    phb
    pea $8080                      ; data bank $80: low RAM and hardware registers by absolute address
    plb
    plb
    rep #$30
    phx
    phy
    lda $0998
    cmp #$0008                     ; main gameplay only
    bne .done
    lda.l $7E0000+!wram_mw_state
    bne .spawned
    jsr receive_next
    bra .done
.spawned:
    jsr trigger_spawned
.done:
    ply
    plx
    plb
    plp
    jml !plm_handler               ; the call we replaced; it returns to the game loop

; If the mailbox holds the next item, spawn its item PLM on Samus.
receive_next:
    lda.l $7E0000+!wram_mailbox_seq
    dec
    cmp.l $7E0000+!wram_received_count
    beq .item
    rts
.item:
    lda.l $7E0000+!wram_mailbox_item
    cmp.w #!items_count            ; .w: asar sizes immediates from defines by value
    bcs skip_item
    cmp.w #!items_nothing
    beq skip_item
    ldx #$004E                     ; a free PLM slot
.free_slot:
    ldy !plm_ids,x
    beq .spawn
    dex
    dex
    bpl .free_slot
    rts                            ; none: again next frame
.spawn:
    asl
    phx
    tax
    lda.l plm_by_item,x
    plx
    jsr spawn_item_plm
    txa
    sta.l $7E0000+!wram_mw_slot
    lda #$0001
    sta.l $7E0000+!wram_mw_state
    rts

skip_item:                         ; an item the ROM can't give: count it as received
    lda.l $7E0000+!wram_received_count
    inc
    sta.l $7E0000+!wram_received_count
    rts

; Spawn item PLM A in PLM slot X at Samus's block, as the vanilla spawn ($84:84E7) does, with a negative room
; argument (the pickup sets no item-collected bit). Keeps X.
spawn_item_plm:
    sta !plm_ids,x
    tay
    ; Samus's block: (y / 16) * room width + x / 16
    lda !samus_y
    lsr
    lsr
    lsr
    lsr
    sep #$20
    sta $4202                      ; hardware multiplier
    lda !room_width_blocks
    sta $4203
    rep #$20
    lda !samus_x
    lsr
    lsr
    lsr
    lsr
    clc
    adc $4216
    asl
    sta !plm_block_indices,x
    lda #$853D                     ; pre-instruction: none (an RTS)
    sta !plm_pre_instructions,x
    phb
    pea $8484
    plb
    plb
    lda $0002,y                    ; the PLM header's instruction list
    plb
    sta !plm_instruction_lists,x
    lda #$0001
    sta.l !plm_timers,x
    lda #$8DA0                     ; draw instruction: none
    sta.l !plm_draw_instructions,x
    lda #$0000
    sta !plm_1d77,x
    sta.l !plm_item_gfx_indices,x
    lda #$8000
    sta !plm_room_arguments,x
    stx $1C27                      ; current PLM index, which setups read
    phx
    tyx                            ; the setup: X = PLM id, Y = PLM slot
    ply
    phy
    jsl call_plm_setup
    plx
    rts

; Once the spawned PLM waits to be touched, go to its pickup (the link instruction) now.
trigger_spawned:
    lda.l $7E0000+!wram_mw_slot
    tax
    lda !plm_pre_instructions,x
    cmp.w #!wait_for_trigger
    bne .return
    lda.l !plm_link_instructions,x
    sta !plm_instruction_lists,x
    lda #$0001
    sta.l !plm_timers,x
    lda #$0000
    sta.l $7E0000+!wram_mw_state
    jmp skip_item                  ; count it as received
.return:
    rts

; Visible item PLM per Map Rando item id (Map Rando's patch.rs `item_to_plm_type`, no container).
plm_by_item:
    dw $EED7, $EEDB, $EEDF, $EEE3, $EEE7, $EEEB, $EEEF, $EEF3, $EEF7, $EEFB, $EEFF, $EF03, $EF07, $EF0B, $EF0F
    dw $EF13, $EF17, $EF1B, $EF1F, $EF23, $EF27, $F000, $EEDB, $F0E2, $F0EE

; Runs the setup of PLM id X for PLM slot Y (JSL). Setups are bank $84 subroutines (RTS), run with data bank $84:
; this one returns through the RTL that ends the PLM handler ($84:85D9), so it needs no code in bank $84.
call_plm_setup:
    phb
    pea $8484
    plb
    plb
    lda.l $840000,x                ; the setup: the first word of the PLM header
    sta $12
    lda #$0084
    sta $14
    phk
    per .return-1
    pea.w !plm_handler_rtl-1
    jml [$0012]
.return:
    plb
    rtl

assert pc() <= !rom_code_end
