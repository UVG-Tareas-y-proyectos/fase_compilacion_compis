# Rutinas MIPS de apoyo. Valores: tag + payload; float en +8 (double).
# 0 null, 1 integer, 2 boolean, 3 float, 4 string,
# 5 lista, 6 closure, 7 clase, 8 instancia.
.data
.align 3
__cs_null: .word 0, 0, 0, 0
__cs_false: .word 2, 0, 0, 0
__cs_true: .word 2, 1, 0, 0
__cs_handler: .word 0
__cs_exception: .word 0
__cs_depth: .word 0
__cs_line: .word 0
__cs_column: .word 0
__cs_s_true: .asciiz "true"
__cs_s_false: .asciiz "false"
__cs_s_null: .asciiz "null"
__cs_s_ref: .asciiz "<referencia>"
__cs_s_prefix: .asciiz "Error MIPS L"
__cs_s_col: .asciiz ":C"
__cs_s_sep: .asciiz ": "
__cs_msg_zero: .asciiz "división entre cero"
__cs_msg_type: .asciiz "tipo inválido en operación MIPS"
__cs_msg_uninit: .asciiz "valor no inicializado"
__cs_msg_this: .asciiz "this no tiene receptor"
__cs_msg_arity: .asciiz "cantidad de argumentos inválida"
__cs_msg_callable: .asciiz "se intentó ejecutar un valor que no es una closure"
__cs_msg_depth: .asciiz "se excedió el límite de profundidad de llamadas"
__cs_msg_index: .asciiz "índice fuera de rango"
__cs_msg_overflow: .asciiz "desbordamiento de integer MIPS32"
__cs_msg_float: .asciiz "resultado float no finito"
.text

# Reservas de tamaño múltiplo de ocho mantienen double alineado.
__cs_box:
    move $t8, $a0
    move $t9, $a1
    li $a0, 16
    li $v0, 9
    syscall
    sw $t9, 0($v0)
    sw $t8, 4($v0)
    sw $zero, 8($v0)
    sw $zero, 12($v0)
    jr $ra
    nop
__cs_box_float:
    mfc1 $t8, $f1
    li $t9, 0x7ff00000
    and $t8, $t8, $t9
    beq $t8, $t9, __cs_err_float
    li $a0, 16
    li $v0, 9
    syscall
    li $t8, 3
    sw $t8, 0($v0)
    sw $zero, 4($v0)
    sdc1 $f0, 8($v0)
    jr $ra
    nop
__cs_env_new:
    move $t8, $a0
    li $a0, 16
    li $v0, 9
    syscall
    sw $t8, 0($v0)
    sw $zero, 4($v0)
    jr $ra
    nop
__cs_declare:
    move $t8, $a0
    move $t9, $a1
    li $a0, 16
    li $v0, 9
    syscall
    sw $t9, 0($v0)
    la $t0, __cs_null
    sw $t0, 4($v0)
    lw $t0, 4($t8)
    sw $t0, 8($v0)
    sw $v0, 4($t8)
    jr $ra
    nop
__cs_get:
    beq $a0, $zero, __cs_err_uninit
    lw $t0, 4($a0)
__cs_get_cell:
    beq $t0, $zero, __cs_get_parent
    lw $t1, 0($t0)
    beq $t1, $a1, __cs_get_found
    lw $t0, 8($t0)
    j __cs_get_cell
__cs_get_parent:
    lw $a0, 0($a0)
    j __cs_get
__cs_get_found:
    lw $v0, 4($t0)
    jr $ra
    nop
__cs_set:
    beq $a0, $zero, __cs_err_uninit
    lw $t0, 4($a0)
__cs_set_cell:
    beq $t0, $zero, __cs_set_parent
    lw $t1, 0($t0)
    beq $t1, $a1, __cs_set_found
    lw $t0, 8($t0)
    j __cs_set_cell
__cs_set_parent:
    lw $a0, 0($a0)
    j __cs_set
__cs_set_found:
    sw $a2, 4($t0)
    move $v0, $a2
    jr $ra
    nop
__cs_closure:
    move $t0, $a0
    move $t1, $a1
    move $t2, $a2
    li $a0, 16
    li $v0, 9
    syscall
    li $t3, 6
    sw $t3, 0($v0)
    sw $t0, 4($v0)
    sw $t1, 8($v0)
    sw $t2, 12($v0)
    jr $ra
    nop

__cs_add:
    li $a2, 0
    j __cs_binary
__cs_sub:
    li $a2, 1
    j __cs_binary
__cs_mul:
    li $a2, 2
    j __cs_binary
__cs_div:
    li $a2, 3
    j __cs_binary
__cs_mod:
    li $a2, 4
    j __cs_binary
__cs_eq:
    li $a2, 5
    j __cs_binary
__cs_ne:
    li $a2, 6
    j __cs_binary
__cs_lt:
    li $a2, 7
    j __cs_binary
__cs_le:
    li $a2, 8
    j __cs_binary
__cs_gt:
    li $a2, 9
    j __cs_binary
__cs_ge:
    li $a2, 10
    j __cs_binary
__cs_binary:
    addiu $sp, $sp, -24
    sw $ra, 0($sp)
    sw $a0, 4($sp)
    sw $a1, 8($sp)
    sw $a2, 12($sp)
    lw $t0, 0($a0)
    lw $t1, 0($a1)
    beq $t0, 4, __cs_binary_string
    beq $t0, 1, __cs_binary_numeric
    beq $t0, 3, __cs_binary_numeric
    j __cs_binary_reference
__cs_binary_string:
    bne $t1, 4, __cs_binary_reference
    beq $a2, $zero, __cs_binary_concat
    blt $a2, 5, __cs_err_type
    lw $a0, 4($a0)
    lw $a1, 4($a1)
    jal __cs_strcmp
    lw $a2, 12($sp)
    beq $a2, 5, __cs_cmp_zero_eq
    beq $a2, 6, __cs_cmp_zero_ne
    beq $a2, 7, __cs_cmp_zero_lt
    beq $a2, 8, __cs_cmp_zero_le
    beq $a2, 9, __cs_cmp_zero_gt
    sge $t0, $v0, $zero
    j __cs_binary_bool
__cs_cmp_zero_eq:
    seq $t0, $v0, $zero
    j __cs_binary_bool
__cs_cmp_zero_ne:
    sne $t0, $v0, $zero
    j __cs_binary_bool
__cs_cmp_zero_lt:
    slt $t0, $v0, $zero
    j __cs_binary_bool
__cs_cmp_zero_le:
    sle $t0, $v0, $zero
    j __cs_binary_bool
__cs_cmp_zero_gt:
    sgt $t0, $v0, $zero
    j __cs_binary_bool
__cs_binary_concat:
    jal __cs_concat
    j __cs_binary_done
__cs_binary_numeric:
    beq $t1, 1, __cs_numeric_ready
    bne $t1, 3, __cs_binary_reference
__cs_numeric_ready:
    bge $a2, 5, __cs_numeric_double
    bne $t0, 1, __cs_numeric_double
    bne $t1, 1, __cs_numeric_double
    lw $t2, 4($a0)
    lw $t3, 4($a1)
    beq $a2, 0, __cs_int_add
    beq $a2, 1, __cs_int_sub
    beq $a2, 2, __cs_int_mul
    beq $t3, $zero, __cs_err_zero
    li $t4, -2147483648
    bne $t2, $t4, __cs_int_div_safe
    li $t4, -1
    beq $t3, $t4, __cs_err_overflow
__cs_int_div_safe:
    div $t2, $t3
    beq $a2, 3, __cs_int_quotient
    mfhi $a0
    j __cs_int_box
__cs_int_quotient:
    mflo $a0
    j __cs_int_box
__cs_int_add:
    addu $a0, $t2, $t3
    xor $t4, $t2, $t3
    bltz $t4, __cs_int_box
    xor $t4, $t2, $a0
    bltz $t4, __cs_err_overflow
    j __cs_int_box
__cs_int_sub:
    subu $a0, $t2, $t3
    xor $t4, $t2, $t3
    bgez $t4, __cs_int_box
    xor $t4, $t2, $a0
    bltz $t4, __cs_err_overflow
    j __cs_int_box
__cs_int_mul:
    mult $t2, $t3
    mflo $a0
    mfhi $t4
    sra $t5, $a0, 31
    bne $t4, $t5, __cs_err_overflow
__cs_int_box:
    li $a1, 1
    jal __cs_box
    j __cs_binary_done
__cs_numeric_double:
    beq $t0, 3, __cs_double_left
    lw $t2, 4($a0)
    mtc1 $t2, $f0
    cvt.d.w $f0, $f0
    j __cs_double_right_test
__cs_double_left:
    ldc1 $f0, 8($a0)
__cs_double_right_test:
    beq $t1, 3, __cs_double_right
    lw $t2, 4($a1)
    mtc1 $t2, $f2
    cvt.d.w $f2, $f2
    j __cs_double_ready
__cs_double_right:
    ldc1 $f2, 8($a1)
__cs_double_ready:
    beq $a2, 0, __cs_float_add
    beq $a2, 1, __cs_float_sub
    beq $a2, 2, __cs_float_mul
    beq $a2, 5, __cs_float_eq
    beq $a2, 6, __cs_float_ne
    beq $a2, 7, __cs_float_lt
    beq $a2, 8, __cs_float_le
    beq $a2, 9, __cs_float_gt
    beq $a2, 10, __cs_float_ge
    mtc1 $zero, $f4
    cvt.d.w $f4, $f4
    c.eq.d $f2, $f4
    bc1t __cs_err_zero
    div.d $f4, $f0, $f2
    beq $a2, 3, __cs_float_div_result
    # Residuo sin convertir el cociente a un entero de 32 bits.
    abs.d $f6, $f0
    abs.d $f8, $f2
    mov.d $f10, $f8
    li $t2, 2
    mtc1 $t2, $f12
    cvt.d.w $f12, $f12
__cs_float_mod_scale:
    mul.d $f14, $f10, $f12
    c.le.d $f14, $f6
    bc1f __cs_float_mod_reduce
    mov.d $f10, $f14
    j __cs_float_mod_scale
__cs_float_mod_reduce:
    c.lt.d $f10, $f8
    bc1t __cs_float_mod_sign
    c.lt.d $f6, $f10
    bc1t __cs_float_mod_half
    sub.d $f6, $f6, $f10
__cs_float_mod_half:
    div.d $f10, $f10, $f12
    j __cs_float_mod_reduce
__cs_float_mod_sign:
    mfc1 $t2, $f1
    bgez $t2, __cs_float_mod_positive
    neg.d $f6, $f6
__cs_float_mod_positive:
    mov.d $f0, $f6
    j __cs_float_box
__cs_float_div_result:
    mov.d $f0, $f4
    j __cs_float_box
__cs_float_add:
    add.d $f0, $f0, $f2
    j __cs_float_box
__cs_float_sub:
    sub.d $f0, $f0, $f2
    j __cs_float_box
__cs_float_mul:
    mul.d $f0, $f0, $f2
__cs_float_box:
    jal __cs_box_float
    j __cs_binary_done
__cs_float_eq:
    c.eq.d $f0, $f2
    bc1t __cs_binary_true
    j __cs_binary_false
__cs_float_ne:
    c.eq.d $f0, $f2
    bc1f __cs_binary_true
    j __cs_binary_false
__cs_float_lt:
    c.lt.d $f0, $f2
    bc1t __cs_binary_true
    j __cs_binary_false
__cs_float_le:
    c.le.d $f0, $f2
    bc1t __cs_binary_true
    j __cs_binary_false
__cs_float_gt:
    c.lt.d $f2, $f0
    bc1t __cs_binary_true
    j __cs_binary_false
__cs_float_ge:
    c.le.d $f2, $f0
    bc1t __cs_binary_true
    j __cs_binary_false
__cs_binary_reference:
    blt $a2, 5, __cs_err_type
    bgt $a2, 6, __cs_err_type
    bne $t0, $t1, __cs_reference_different
    beq $t0, 0, __cs_reference_same
    beq $t0, 2, __cs_reference_bool
    seq $t0, $a0, $a1
    j __cs_reference_result
__cs_reference_bool:
    lw $t0, 4($a0)
    lw $t1, 4($a1)
    seq $t0, $t0, $t1
    j __cs_reference_result
__cs_reference_same:
    li $t0, 1
    j __cs_reference_result
__cs_reference_different:
    move $t0, $zero
__cs_reference_result:
    beq $a2, 5, __cs_binary_bool
    xori $t0, $t0, 1
__cs_binary_bool:
    bne $t0, $zero, __cs_binary_true
__cs_binary_false:
    la $v0, __cs_false
    j __cs_binary_done
__cs_binary_true:
    la $v0, __cs_true
__cs_binary_done:
    lw $ra, 0($sp)
    addiu $sp, $sp, 24
    jr $ra
    nop

__cs_neg:
    lw $t0, 0($a0)
    beq $t0, 3, __cs_neg_double
    bne $t0, 1, __cs_err_type
    lw $t0, 4($a0)
    li $t1, -2147483648
    beq $t0, $t1, __cs_err_overflow
    subu $a0, $zero, $t0
    li $a1, 1
    j __cs_box
__cs_neg_double:
    ldc1 $f0, 8($a0)
    neg.d $f0, $f0
    j __cs_box_float
__cs_i2f:
    lw $t0, 4($a0)
    mtc1 $t0, $f0
    cvt.d.w $f0, $f0
    j __cs_box_float
__cs_not:
    addiu $sp, $sp, -8
    sw $ra, 0($sp)
    jal __cs_truth
    beq $v0, $zero, __cs_not_true
    la $v0, __cs_false
    j __cs_not_done
__cs_not_true:
    la $v0, __cs_true
__cs_not_done:
    lw $ra, 0($sp)
    addiu $sp, $sp, 8
    jr $ra
    nop
__cs_truth:
    lw $t0, 0($a0)
    beq $t0, 0, __cs_truth_false
    beq $t0, 3, __cs_truth_double
    beq $t0, 4, __cs_truth_string
    ble $t0, 2, __cs_truth_payload
    beq $t0, 5, __cs_truth_payload
    li $v0, 1
    jr $ra
    nop
__cs_truth_payload:
    lw $t0, 4($a0)
    sne $v0, $t0, $zero
    jr $ra
    nop
__cs_truth_string:
    lw $t0, 4($a0)
    lbu $t0, 0($t0)
    sne $v0, $t0, $zero
    jr $ra
    nop
__cs_truth_double:
    ldc1 $f0, 8($a0)
    mtc1 $zero, $f2
    cvt.d.w $f2, $f2
    c.eq.d $f0, $f2
    bc1t __cs_truth_false
    li $v0, 1
    jr $ra
    nop
__cs_truth_false:
    move $v0, $zero
    jr $ra
    nop

__cs_strcmp:
    lbu $t0, 0($a0)
    lbu $t1, 0($a1)
    bne $t0, $t1, __cs_strcmp_different
    beq $t0, $zero, __cs_strcmp_equal
    addiu $a0, $a0, 1
    addiu $a1, $a1, 1
    j __cs_strcmp
__cs_strcmp_different:
    subu $v0, $t0, $t1
    jr $ra
    nop
__cs_strcmp_equal:
    move $v0, $zero
    jr $ra
    nop
__cs_concat:
    addiu $sp, $sp, -24
    sw $ra, 0($sp)
    lw $t0, 4($a0)
    lw $t1, 4($a1)
    sw $t0, 4($sp)
    sw $t1, 8($sp)
    move $t2, $zero
    move $t3, $t0
__cs_concat_size1:
    lbu $t4, 0($t3)
    beq $t4, $zero, __cs_concat_size2_start
    addiu $t2, $t2, 1
    addiu $t3, $t3, 1
    j __cs_concat_size1
__cs_concat_size2_start:
    move $t3, $t1
__cs_concat_size2:
    lbu $t4, 0($t3)
    beq $t4, $zero, __cs_concat_allocate
    addiu $t2, $t2, 1
    addiu $t3, $t3, 1
    j __cs_concat_size2
__cs_concat_allocate:
    addiu $a0, $t2, 8
    li $t4, -8
    and $a0, $a0, $t4
    li $v0, 9
    syscall
    sw $v0, 12($sp)
    move $t3, $v0
    lw $t0, 4($sp)
__cs_concat_copy1:
    lbu $t4, 0($t0)
    beq $t4, $zero, __cs_concat_copy2_start
    sb $t4, 0($t3)
    addiu $t0, $t0, 1
    addiu $t3, $t3, 1
    j __cs_concat_copy1
__cs_concat_copy2_start:
    lw $t0, 8($sp)
__cs_concat_copy2:
    lbu $t4, 0($t0)
    sb $t4, 0($t3)
    beq $t4, $zero, __cs_concat_done
    addiu $t0, $t0, 1
    addiu $t3, $t3, 1
    j __cs_concat_copy2
__cs_concat_done:
    lw $a0, 12($sp)
    li $a1, 4
    jal __cs_box
    lw $ra, 0($sp)
    addiu $sp, $sp, 24
    jr $ra
    nop

__cs_print:
    addiu $sp, $sp, -8
    sw $ra, 0($sp)
    jal __cs_show
    li $a0, 10
    li $v0, 11
    syscall
    lw $ra, 0($sp)
    addiu $sp, $sp, 8
    jr $ra
    nop
__cs_show:
    lw $t0, 0($a0)
    beq $t0, 0, __cs_show_null
    beq $t0, 1, __cs_show_int
    beq $t0, 2, __cs_show_bool
    beq $t0, 3, __cs_show_float
    beq $t0, 4, __cs_show_string
    beq $t0, 5, __cs_show_list
    beq $t0, 6, __cs_show_closure
    beq $t0, 8, __cs_show_object
    la $a0, __cs_s_ref
    li $v0, 4
    syscall
    jr $ra
    nop
__cs_show_null:
    la $a0, __cs_s_null
    j __cs_show_raw
__cs_show_int:
    lw $a0, 4($a0)
    li $v0, 1
    syscall
    jr $ra
    nop
__cs_show_bool:
    lw $t0, 4($a0)
    la $a0, __cs_s_false
    beq $t0, $zero, __cs_show_raw
    la $a0, __cs_s_true
    j __cs_show_raw
__cs_show_float:
    ldc1 $f12, 8($a0)
    li $v0, 3
    syscall
    jr $ra
    nop
__cs_show_string:
    lw $a0, 4($a0)
__cs_show_raw:
    li $v0, 4
    syscall
    jr $ra
    nop

# Los manejadores guardan el punto de retorno y el estado de la activación.
__cs_try:
    move $t8, $a0
    li $a0, 32
    li $v0, 9
    syscall
    lw $t0, __cs_handler
    sw $t0, 0($v0)
    sw $t8, 4($v0)
    sw $sp, 8($v0)
    sw $fp, 12($v0)
    sw $s0, 16($v0)
    sw $s1, 20($v0)
    lw $t0, __cs_depth
    sw $t0, 24($v0)
    sw $v0, __cs_handler
    jr $ra
    nop
__cs_err_zero:
    la $a0, __cs_msg_zero
    j __cs_fail
__cs_err_type:
    la $a0, __cs_msg_type
    j __cs_fail
__cs_err_uninit:
    la $a0, __cs_msg_uninit
    j __cs_fail
__cs_err_this:
    la $a0, __cs_msg_this
    j __cs_fail
__cs_err_arity:
    la $a0, __cs_msg_arity
    j __cs_fail
__cs_err_callable:
    la $a0, __cs_msg_callable
    j __cs_fail
__cs_err_depth:
    la $a0, __cs_msg_depth
    j __cs_fail
__cs_err_index:
    la $a0, __cs_msg_index
    j __cs_fail
__cs_err_overflow:
    la $a0, __cs_msg_overflow
    j __cs_fail
__cs_err_float:
    la $a0, __cs_msg_float
__cs_fail:
    addiu $sp, $sp, -8
    sw $a0, 0($sp)
    li $a1, 4
    jal __cs_box
    sw $v0, __cs_exception
    lw $t0, __cs_handler
    beq $t0, $zero, __cs_fail_uncaught
    lw $t1, 0($t0)
    sw $t1, __cs_handler
    lw $t9, 4($t0)
    lw $sp, 8($t0)
    lw $fp, 12($t0)
    lw $s0, 16($t0)
    lw $s1, 20($t0)
    lw $t1, 24($t0)
    sw $t1, __cs_depth
    jr $t9
    nop
__cs_fail_uncaught:
    la $a0, __cs_s_prefix
    li $v0, 4
    syscall
    lw $a0, __cs_line
    li $v0, 1
    syscall
    la $a0, __cs_s_col
    li $v0, 4
    syscall
    lw $a0, __cs_column
    li $v0, 1
    syscall
    la $a0, __cs_s_sep
    li $v0, 4
    syscall
    lw $a0, 0($sp)
    li $v0, 4
    syscall
    li $a0, 10
    li $v0, 11
    syscall
    li $a0, 1
    li $v0, 17
    syscall

.data
__cs_s_comma: .asciiz ", "
__cs_s_closure: .asciiz "<closure "
__cs_msg_method: .asciiz "método inexistente"
__cs_index_prefix: .asciiz "índice fuera de rango: "
.align 3
__cs_index_prefix_value: .word 4, __cs_index_prefix, 0, 0
.text
__cs_newlist:
    move $t0, $a0
    sll $a0, $t0, 2
    addiu $a0, $a0, 8
    li $t2, -8
    and $a0, $a0, $t2
    li $v0, 9
    syscall
    move $t1, $v0
    move $t2, $zero
    la $t4, __cs_null
__cs_newlist_init:
    bge $t2, $t0, __cs_newlist_box
    sll $t3, $t2, 2
    addu $t3, $t3, $t1
    sw $t4, 0($t3)
    addiu $t2, $t2, 1
    j __cs_newlist_init
__cs_newlist_box:
    li $a0, 16
    li $v0, 9
    syscall
    li $t2, 5
    sw $t2, 0($v0)
    sw $t0, 4($v0)
    sw $t1, 8($v0)
    jr $ra
    nop
__cs_length:
    lw $t0, 0($a0)
    beq $t0, 4, __cs_length_string
    bne $t0, 5, __cs_err_type
    lw $a0, 4($a0)
    li $a1, 1
    j __cs_box
__cs_length_string:
    lw $t0, 4($a0)
    move $a0, $zero
__cs_length_loop:
    lbu $t1, 0($t0)
    beq $t1, $zero, __cs_length_done
    addiu $a0, $a0, 1
    addiu $t0, $t0, 1
    j __cs_length_loop
__cs_length_done:
    li $a1, 1
    j __cs_box
__cs_index_address:
    lw $t0, 0($a0)
    bne $t0, 5, __cs_err_type
    lw $t0, 0($a1)
    bne $t0, 1, __cs_err_type
    lw $t2, 4($a1)
    bltz $t2, __cs_index_fail
    lw $t0, 4($a0)
    bge $t2, $t0, __cs_index_fail
    lw $t0, 8($a0)
    sll $t2, $t2, 2
    addu $v0, $t0, $t2
    jr $ra
    nop
__cs_load_index:
    addiu $sp, $sp, -8
    sw $ra, 0($sp)
    jal __cs_index_address
    lw $v0, 0($v0)
    lw $ra, 0($sp)
    addiu $sp, $sp, 8
    jr $ra
    nop
__cs_store_index:
    addiu $sp, $sp, -8
    sw $ra, 0($sp)
    jal __cs_index_address
    sw $a2, 0($v0)
    lw $ra, 0($sp)
    addiu $sp, $sp, 8
    jr $ra
    nop
# Conversión decimal de un entero para mensajes de error.
__cs_int_string:
    move $t0, $a0
    li $a0, 32
    li $v0, 9
    syscall
    addiu $t1, $v0, 31
    sb $zero, 0($t1)
    slt $t4, $t0, $zero
    beq $t4, $zero, __cs_int_string_loop
    subu $t0, $zero, $t0
__cs_int_string_loop:
    li $t2, 10
    divu $t0, $t2
    mfhi $t3
    mflo $t0
    addiu $t3, $t3, 48
    addiu $t1, $t1, -1
    sb $t3, 0($t1)
    bne $t0, $zero, __cs_int_string_loop
    beq $t4, $zero, __cs_int_string_done
    addiu $t1, $t1, -1
    li $t3, 45
    sb $t3, 0($t1)
__cs_int_string_done:
    move $v0, $t1
    jr $ra
    nop
__cs_index_fail:
    move $a0, $t2
    jal __cs_int_string
    move $a0, $v0
    li $a1, 4
    jal __cs_box
    move $a1, $v0
    la $a0, __cs_index_prefix_value
    jal __cs_concat
    lw $a0, 4($v0)
    j __cs_fail

__cs_class:
    move $t0, $a0
    move $t1, $a1
    move $t2, $a2
    li $a0, 16
    li $v0, 9
    syscall
    li $t3, 7
    sw $t3, 0($v0)
    sw $t0, 4($v0)
    sw $t1, 8($v0)
    sw $t2, 12($v0)
    jr $ra
    nop
__cs_load_field:
    lw $t0, 0($a0)
    bne $t0, 8, __cs_err_type
    lw $a0, 8($a0)
    j __cs_get
__cs_store_field:
    lw $t0, 0($a0)
    bne $t0, 8, __cs_err_type
    addiu $sp, $sp, -24
    sw $ra, 0($sp)
    lw $a0, 8($a0)
    sw $a0, 4($sp)
    sw $a1, 8($sp)
    sw $a2, 12($sp)
    lw $t0, 4($a0)
__cs_field_find:
    beq $t0, $zero, __cs_field_declare
    lw $t1, 0($t0)
    beq $t1, $a1, __cs_field_set
    lw $t0, 8($t0)
    j __cs_field_find
__cs_field_declare:
    jal __cs_declare
__cs_field_set:
    lw $a0, 4($sp)
    lw $a1, 8($sp)
    lw $a2, 12($sp)
    jal __cs_set
    lw $ra, 0($sp)
    addiu $sp, $sp, 24
    jr $ra
    nop
__cs_method:
    move $t6, $a0
    lw $t0, 0($a0)
    bne $t0, 8, __cs_err_type
    lw $t0, 4($a0)
__cs_method_class:
    lw $t1, 0($t0)
    bne $t1, 7, __cs_method_missing
    lw $t1, 4($t0)
    lw $t2, 4($t1)
    addiu $t3, $t1, 12
__cs_method_search:
    beq $t2, $zero, __cs_method_parent
    lw $t4, 0($t3)
    beq $t4, $a1, __cs_method_found
    addiu $t3, $t3, 8
    addiu $t2, $t2, -1
    j __cs_method_search
__cs_method_parent:
    lw $t0, 12($t0)
    j __cs_method_class
__cs_method_found:
    lw $a0, 4($t3)
    lw $a1, 8($t0)
    move $a2, $t6
    j __cs_closure
__cs_method_missing:
    la $a0, __cs_msg_method
    j __cs_fail
__cs_new:
    lw $t0, 0($a0)
    bne $t0, 7, __cs_err_type
    addiu $sp, $sp, -24
    sw $ra, 0($sp)
    sw $a0, 4($sp)
    li $a0, 16
    li $v0, 9
    syscall
    li $t0, 8
    sw $t0, 0($v0)
    lw $t0, 4($sp)
    sw $t0, 4($v0)
    sw $v0, 8($sp)
    move $a0, $zero
    jal __cs_env_new
    lw $t0, 8($sp)
    sw $v0, 8($t0)
    lw $a0, 4($sp)
    move $a1, $t0
    jal __cs_init_chain
    lw $v0, 8($sp)
    lw $ra, 0($sp)
    addiu $sp, $sp, 24
    jr $ra
    nop
# Inicializar la clase padre antes de la hija, sobre el mismo objeto.
__cs_init_chain:
    addiu $sp, $sp, -24
    sw $ra, 0($sp)
    sw $a0, 4($sp)
    sw $a1, 8($sp)
    lw $a0, 12($a0)
    lw $t0, 0($a0)
    bne $t0, 7, __cs_init_own
    jal __cs_init_chain
__cs_init_own:
    lw $t0, 4($sp)
    lw $t1, 4($t0)
    lw $a0, 0($t1)
    lw $a1, 8($t0)
    lw $a2, 8($sp)
    jal __cs_closure
    move $a0, $v0
    move $a1, $zero
    move $a2, $zero
    lw $t9, 4($a0)
    jalr $t9
    lw $ra, 0($sp)
    addiu $sp, $sp, 24
    jr $ra
    nop

__cs_show_list:
    addiu $sp, $sp, -16
    sw $ra, 0($sp)
    sw $a0, 4($sp)
    sw $zero, 8($sp)
    li $a0, 91
    li $v0, 11
    syscall
__cs_show_list_loop:
    lw $t0, 4($sp)
    lw $t1, 8($sp)
    lw $t2, 4($t0)
    bge $t1, $t2, __cs_show_list_end
    beq $t1, $zero, __cs_show_list_item
    la $a0, __cs_s_comma
    li $v0, 4
    syscall
__cs_show_list_item:
    lw $t2, 8($t0)
    sll $t3, $t1, 2
    addu $t2, $t2, $t3
    lw $a0, 0($t2)
    jal __cs_show
    lw $t1, 8($sp)
    addiu $t1, $t1, 1
    sw $t1, 8($sp)
    j __cs_show_list_loop
__cs_show_list_end:
    li $a0, 93
    li $v0, 11
    syscall
    lw $ra, 0($sp)
    addiu $sp, $sp, 16
    jr $ra
    nop
__cs_show_object:
    lw $t0, 4($a0)
    lw $t0, 4($t0)
    lw $t0, 8($t0)
    li $a0, 60
    li $v0, 11
    syscall
    move $a0, $t0
    li $v0, 4
    syscall
    li $a0, 62
    li $v0, 11
    syscall
    jr $ra
    nop
__cs_show_closure:
    lw $t0, 4($a0)
    la $t1, __cs_fn_names
    lw $t2, 0($t1)
    addiu $t1, $t1, 4
__cs_show_closure_find:
    beq $t2, $zero, __cs_show_closure_end
    lw $t3, 0($t1)
    beq $t3, $t0, __cs_show_closure_name
    addiu $t1, $t1, 8
    addiu $t2, $t2, -1
    j __cs_show_closure_find
__cs_show_closure_name:
    lw $t0, 4($t1)
    la $a0, __cs_s_closure
    li $v0, 4
    syscall
    move $a0, $t0
    li $v0, 4
    syscall
__cs_show_closure_end:
    li $a0, 62
    li $v0, 11
    syscall
    jr $ra
    nop
