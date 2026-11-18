from desktop_toys import ToyBrain, YarnPhysics

AREA = (0, 0, 1000, 700)


def _run(ball, seconds, platforms=()):
    for _ in range(int(seconds * 60)):
        ball.step(1 / 60, AREA, platforms)


def test_yarn_bounces_off_walls_and_comes_to_rest_on_floor():
    ball = YarnPhysics(900, 300)
    ball.push(1500, -300)
    _run(ball, 0.5)
    assert ball.vx < 0                          # sağ kenardan sekti
    _run(ball, 12)
    assert ball.resting and abs(ball.y + ball.r - 700) < 1e-6
    assert 0 + ball.r <= ball.x <= 1000 - ball.r


def test_yarn_lands_on_window_top_only_when_falling_onto_it():
    ball = YarnPhysics(500, 100)
    _run(ball, 3, platforms=[(300, 400, 800)])
    assert ball.resting and abs(ball.y + ball.r - 400) < 1e-6
    below = YarnPhysics(500, 600)                # pencere kenarının altında başlayan top yere düşer
    _run(below, 3, platforms=[(300, 400, 800)])
    assert abs(below.y + below.r - 700) < 1e-6


def test_toy_brain_bats_goes_drinks_and_respects_play_window():
    brain = ToyBrain()
    toys = {"yarn": (520, 700)}
    assert brain.decide(10, (100, 640), True, 0, toys) is None      # atılmadan ilgi yok
    brain.user_threw(10)
    assert brain.decide(11, (100, 640), True, 0, toys)["action"] == "go"
    bat = brain.decide(12, (500, 660), False, 0, toys)
    assert bat["action"] == "bat" and bat["vx"] > 0 and bat["vy"] < 0
    assert brain.decide(12.5, (500, 660), False, 0, toys) is None   # pati bekleme süresi
    assert brain.decide(10 + brain.PLAY_WINDOW + 1, (500, 660), True, 0, toys) is None
    bowl = {"bowl": (130, 700)}
    assert brain.decide(100, (100, 640), True, 20, bowl) is None    # tok
    assert brain.decide(100, (100, 640), True, 80, bowl)["action"] == "drink"
    assert brain.decide(101, (100, 640), True, 80, bowl) is None    # bekleme süresi
