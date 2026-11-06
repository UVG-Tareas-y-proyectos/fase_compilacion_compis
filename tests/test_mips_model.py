import pytest
from compiscript.ir import FunctionCode, Instruction
from compiscript.mips_model import FrameLayout, RegisterAllocator, MIPSError, peephole


def test_frame_is_physical_and_aligned_without_changing_abstract_frame():
    function=FunctionCode('f','f',instructions=[Instruction('param','%t1'),Instruction('call','v0_f','1','%t2')],frame={'tamano':128})
    frame=FrameLayout.build(function)
    assert frame.temporaries=={'%t1':32,'%t2':36}
    assert frame.arguments==[40] and frame.size==48
    assert function.frame=={'tamano':128}


def test_getReg_spills_and_reloads_real_stack_homes():
    lines=[]
    allocator=RegisterAllocator({'%a':32,'%b':36,'%c':40},lines.append,['$t0','$t1'])
    allocator.getReg('%a',write=True)
    allocator.getReg('%b',write=True)
    allocator.getReg('%c',write=True)
    assert 'sw $t0, 32($fp)' in lines
    allocator.getReg('%a')
    assert 'lw $t1, 32($fp)' in lines and allocator.spills==2
    allocator.flush()
    assert not allocator.descriptors


def test_invalid_tac_argument_sequence_is_rejected():
    with pytest.raises(MIPSError,match='insuficientes'):
        FrameLayout.build(FunctionCode('f','f',instructions=[Instruction('call','v0_f','1')]))


def test_peephole_preserves_calls_and_delay_slots():
    assert peephole(['move $t0, $t0','j L1','nop','L1:','jal f','nop'])==['L1:','jal f','nop']
