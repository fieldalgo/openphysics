# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent format oracles and explicit-condition network comparisons."""
import importlib.metadata as metadata

import numpy as np
import pytest

from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import LineNetwork,rlgc_network
from sipi.touchstone import loads_touchstone,compare_networks


def fixture(n=2,version=2,form='ri',unit='hz',matrix='full',order='21_12'):
    # Deliberately nonreciprocal in full format: a transpose cannot pass.
    grid = np.arange(1,n*n+1,dtype=float).reshape(n,n)
    s = (grid+1j*(grid+2))/(2*n*n)
    if matrix != 'full':
        s = (s+s.T)/2
    s = np.stack((s,s*.75))
    f = np.array([1e6,2e6])
    z = np.arange(n)*10+40. if version==2 else np.full(n,50.)
    scale = dict(hz=1,khz=1e3,mhz=1e6,ghz=1e9)[unit]
    lines = ['[Version] 2.0'] if version==2 else []
    lines += [f'# {unit} S {form} R 50']
    if version==2:
        lines += [f'[Number of Ports] {n}','[Number of Frequencies] 2',
                  '[Reference]', ' '.join(map(str,z)),f'[Matrix Format] {matrix}']
        if n==2:
            lines += [f'[Two-Port Data Order] {order}']
        lines += ['[Network Data]']
    for frequency,values in zip(f,s):
        if matrix=='lower':
            sequence=[values[i,j] for i in range(n) for j in range(i+1)]
        elif matrix=='upper':
            sequence=[values[i,j] for i in range(n) for j in range(i,n)]
        elif n==2 and order=='21_12':
            sequence=[values[0,0],values[1,0],values[0,1],values[1,1]]
        else:
            sequence=[values[i,j] for i in range(n) for j in range(n)]
        numbers=[frequency/scale]
        for value in sequence:
            if form=='ri':
                numbers.extend((value.real,value.imag))
            elif form=='ma':
                numbers.extend((abs(value),np.angle(value,deg=True)))
            else:
                numbers.extend((20*np.log10(abs(value)),np.angle(value,deg=True)))
        tokens=[f'{v:.17g}' for v in numbers]
        if version==2 or n>=3:
            # Arbitrary legal whitespace/continuations in the accepted v2 subset.
            lines.extend(' '.join(tokens[i:i+7]) for i in range(0,len(tokens),7))
        else:
            lines.append(' '.join(tokens))
    if version==2:lines.append('[End]')
    return '\n'.join(lines)+'\n',f,s,z


@pytest.mark.parametrize('n',[1,2,3,4])
@pytest.mark.parametrize('form',['ri','ma','db'])
@pytest.mark.parametrize('version',[1,2])
def test_formats_and_nonreciprocal_port_order(n,form,version):
    text,f,s,z=fixture(n,version,form)
    net=loads_touchstone(text,ports=n if version==1 else None)
    np.testing.assert_allclose(net.s,s,atol=1e-12,rtol=0)
    np.testing.assert_array_equal(net.frequency,f)
    np.testing.assert_array_equal(net.z_ref,z)
    assert net.port_names==tuple(f'port{i+1}' for i in range(n))


@pytest.mark.parametrize('unit',['hz','khz','mhz','ghz'])
@pytest.mark.parametrize('order',['21_12','12_21'])
def test_units_and_two_port_orders(unit,order):
    text,f,s,_=fixture(unit=unit,order=order)
    net=loads_touchstone(text)
    np.testing.assert_array_equal(net.frequency,f)
    np.testing.assert_allclose(net.s,s,atol=1e-12,rtol=0)


@pytest.mark.parametrize('n',[2,3,4])
@pytest.mark.parametrize('matrix',['lower','upper'])
def test_triangular_matrices_are_symmetric_not_hermitian(n,matrix):
    text,f,s,_=fixture(n,matrix=matrix)
    net=loads_touchstone(text)
    np.testing.assert_allclose(net.s,s,atol=1e-12,rtol=0)
    assert abs(net.s.imag).max()>0
    np.testing.assert_array_equal(net.s,net.s.swapaxes(1,2))


def test_defaults_comments_information_and_version_whitespace():
    net=loads_touchstone('! comment\n#\n0 1 90 ! phase in degrees\n1 .5 -90\n',ports=1)
    np.testing.assert_allclose(net.s[:,0,0],[1j,-.5j],atol=1e-14)
    np.testing.assert_array_equal(net.frequency,[0,1e9])
    text,f,s,_=fixture()
    text=text.replace('[Version] 2.0','[Version]\t 2.0').replace('# hz S ri R 50','# ri R 50 S hz')
    text=text.replace('[Network Data]','[Begin Information]\narbitrary descriptive text\n[End Information]\n[Network Data]')
    np.testing.assert_allclose(loads_touchstone(text).s,s,atol=1e-12,rtol=0)


@pytest.mark.parametrize('n',[1,2,3,4])
def test_own_export_roundtrip_preserves_arrays_and_explicit_names(n):
    text,f,s,z=fixture(n)
    original=LineNetwork(f,s,z,tuple(f'explicit_{i}' for i in range(n)))
    restored=loads_touchstone(original.touchstone(),port_names=original.port_names)
    np.testing.assert_array_equal(restored.frequency,original.frequency)
    np.testing.assert_allclose(restored.s,original.s,atol=1e-14,rtol=0)
    np.testing.assert_array_equal(restored.z_ref,original.z_ref)
    assert restored.port_names==original.port_names
    assert not restored.s.flags.writeable


def test_independent_skrf_reader_across_supported_formats(tmp_path):
    skrf=require_tool('scikit-rf')
    clock=Stopwatch();errors=[]
    cases=[(2,1,'ma','full','21_12'),(2,2,'db','full','12_21'),
           (3,2,'ri','full','21_12'),(4,2,'ma','lower','21_12'),
           (4,2,'db','upper','21_12')]
    for n,version,form,matrix,order in cases:
        text,f,s,z=fixture(n,version,form,matrix=matrix,order=order)
        path=tmp_path/f'samples.s{n}p';path.write_text(text,encoding='ascii')
        with clock('openphysics'):
            ours=loads_touchstone(text,ports=n)
        with clock('reference'):
            reference=skrf.Network(str(path))
        errors.append(float(np.max(abs(ours.s-reference.s))))
        np.testing.assert_array_equal(ours.frequency,reference.f)
        np.testing.assert_allclose(reference.z0,np.broadcast_to(z,(2,n)),atol=1e-12,rtol=0)
    maximum=max(errors)
    record=make_record(case='sipi-touchstone-input',physics='network sample interchange',
        api='sipi.touchstone.loads_touchstone',discretization='strict single-ended S text parser',
        tool='scikit-rf',tool_discretization='independent Touchstone reader',
        matched=['same synthetic nonreciprocal S files, units, references and order',
                 'v1/v2, RI/MA/DB, full/lower/upper, two/three/four ports'],
        not_matched=['format agreement is not measurement calibration or field accuracy'],
        observables=[observable('S matrix','1','maximum absolute difference',maximum,1e-12)],
        analytical_acceptance='tests/sipi/test_touchstone.py: explicit synthetic matrices and comparison residuals',
        stopwatch=clock)
    record['openphysics']['distribution']='sipi'
    record['openphysics']['version']=metadata.version('sipi')
    emit(record)
    assert maximum<1e-12


@pytest.mark.parametrize('old,new',[
 ('[Version] 2.0','[Version] 3.0'),('[Version] 2.0',' [Version] 2.0'),
 ('# hz S ri R 50','# hz Y ri R 50'),('# hz S ri R 50','# hz S ri R -1'),
 ('# hz S ri R 50','# hz S ri R 50 R 50'),
 ('[Reference]\n40.0 50.0','[Reference]\n40.0'),
 ('[Reference]\n40.0 50.0','[Reference]\n40.0 -50.0'),
 ('[Number of Frequencies] 2','[Number of Frequencies] 3'),
 ('[Number of Ports] 2','[Number of Ports] 2\n[Number of Ports] 2'),
 ('[Matrix Format] full','[Matrix Format] mystery'),
 ('[Matrix Format] full','[Mixed-Mode Order] D1,2 C1,2'),
 ('[Matrix Format] full','[Number of Noise Frequencies] 1'),
 ('[Two-Port Data Order] 21_12',''),('[End]',''),
 ('[End]','[End]\n1 2 3'),('[Network Data]','[Noise Data]'),
 ('1000000','NaN'),('1000000','1e999'),('1000000','1_000_000'),
 ('2000000','1000000'),('1000000','-1'),
])
def test_malformed_and_unsupported_input_is_rejected(old,new):
    text,*_=fixture()
    assert old in text
    with pytest.raises(ValueError):loads_touchstone(text.replace(old,new))


@pytest.mark.parametrize('ports',[None,0,-1,True,2.5])
def test_version_one_requires_explicit_valid_port_count(ports):
    text,*_=fixture(version=1)
    with pytest.raises(ValueError):loads_touchstone(text,ports=ports)


def test_wrong_port_names_count_nonascii_incomplete_and_noise_are_rejected():
    text,*_=fixture()
    for kwargs in (dict(ports=3),dict(port_names=['one']),dict(port_names=['same','same'])):
        with pytest.raises(ValueError):loads_touchstone(text,**kwargs)
    for invalid in ('',text+'! nonascii\N{GREEK SMALL LETTER MU}',text.replace('0.5 0.75','0.5')):
        with pytest.raises(ValueError):loads_touchstone(invalid)
    with pytest.raises(ValueError):loads_touchstone('# hz S ri\n1 0 0 1 0 1 0 0 0\n2 1 .5 0 1\n',ports=2)


def network(f,offset=0):
    f=np.asarray(f,dtype=float)
    s=np.empty((len(f),2,2),dtype=complex)
    s[:]=np.array([[.1+.05j,.2-.1j],[.3+.1j,.15-.02j]])
    s+=f[:,None,None]*(.01+.02j)+offset
    return LineNetwork(f,s,[50,50],('near','far'))


def test_comparison_exact_subset_and_complex_phase_residual():
    measured=network([0,1,2,3]);model=network([1,3],.01j)
    result=compare_networks(measured,model)
    np.testing.assert_allclose(result.delta_s,.01j,atol=1e-14,rtol=0)
    assert result.max_abs_error==pytest.approx(.01,abs=1e-14)
    assert not result.delta_s.flags.writeable
    assert compare_networks(measured,measured).max_abs_error==0


def test_interpolation_is_explicit_linear_complex_and_bounded():
    measured=network([0,2,4]);model=network([1,3])
    with pytest.raises(ValueError,match='absent'):compare_networks(measured,model)
    result=compare_networks(measured,model,interpolation='linear')
    assert result.max_abs_error<1e-12
    for mode in ('none','linear'):
        with pytest.raises(ValueError,match='extrapolate'):
            compare_networks(measured,network([5]),interpolation=mode)
    with pytest.raises(ValueError):compare_networks(measured,model,interpolation='cubic')


@pytest.mark.parametrize('change',['names','basis','reference'])
def test_comparison_rejects_unmatched_physical_conditions(change):
    measured=network([0,1]);a=measured
    other=LineNetwork(a.frequency,a.s,[50,75] if change=='reference' else a.z_ref,
        a.port_names[::-1] if change=='names' else a.port_names,
        'mixed-mode' if change=='basis' else a.basis)
    with pytest.raises(ValueError,match='must match'):compare_networks(measured,other)


def test_calculated_line_and_imported_samples_compare_without_hidden_reordering():
    model=rlgc_network([0,1e6,1e9],R=[[2]],L=[[400e-9]],G=[[.001]],C=[[100e-12]],length=.1)
    measured=loads_touchstone(model.touchstone(),port_names=model.port_names)
    assert compare_networks(measured,model).max_abs_error<1e-14
    with pytest.raises(ValueError,match='port order'):
        compare_networks(loads_touchstone(model.touchstone()),model)
