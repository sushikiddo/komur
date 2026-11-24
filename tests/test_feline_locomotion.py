import math

from feline_locomotion import DUTY, PHASE_OFFSETS, STRIDE, FelineGait, foot_offset, two_bone_ik

HIPS = {"LH": (82, 214), "LF": (184, 216), "RH": (94, 212), "RF": (174, 214)}


def test_ik_bones_keep_length_and_bend_side():
    root, target = (0.0, 0.0), (0.0, 40.0)
    for bend, side in ((1, -1), (-1, 1)):
        j = two_bone_ik(root, target, 24, 24, bend)
        assert math.isclose(math.dist(root, j), 24, abs_tol=1e-6)
        assert math.isclose(math.dist(j, target), 24, abs_tol=1e-6)
        assert j[0] * side < 0          # bend işareti dirseği yanlara ayırır


def test_lateral_sequence_and_no_slip_in_stance():
    assert sorted(PHASE_OFFSETS, key=PHASE_OFFSETS.get) == ["LH", "LF", "RH", "RF"]
    # Duruşta ayak gövdeye göre sabit hızla geri gider ve yerde kalır.
    a, b = foot_offset(0.1), foot_offset(0.2)
    assert a[1] == b[1] == 0.0
    assert math.isclose(a[0] - b[0], STRIDE * 0.1 / DUTY)
    assert foot_offset(DUTY + (1 - DUTY) / 2)[1] > 0      # salınım ortası havada


def test_phase_rate_matches_ground_speed():
    gait = FelineGait()
    gait.advance(0.0, 60)
    gait.advance(0.05, 60)
    # Döngü/sn * duruş yolu = hız  -> ayak yere göre kaymaz
    assert math.isclose(gait.phase / 0.05 * STRIDE / DUTY, 60)


def test_pose_has_four_legs_on_ground_and_hind_z_joint():
    pose = FelineGait().pose(0.0, 60, HIPS, 259)
    assert set(pose.legs) == set(HIPS)
    assert len(pose.legs["LH"].joints) == 4 and len(pose.legs["LF"].joints) == 3
    assert all(leg.foot[1] <= 259 for leg in pose.legs.values())
    assert sum(not leg.lifted for leg in pose.legs.values()) >= 2   # her an en az iki ayak yerde
