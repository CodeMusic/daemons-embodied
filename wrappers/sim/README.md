# wrappers/sim -- a body with no hardware

*DRAFT: every word here waits on the user's approval.*

A body made only of its sheet. It answers every one of the driver's calls, makes up a believable balance reading
from how it is standing, and draws itself as a stick figure in a browser page. Everything above the wrapper is
built and tested against it, with no robot on the desk. **It cannot say whether a gait walks.**

| File | What it is |
|---|---|
| `sheet.yaml` | twelve joints on three channels, six senses, a voice, eleven lights, three postures |
| `actions/` | the ten actions it comes with |
| `driver.py` | the ten calls, and the WORLD: what a hand does to a body (tip it, pat it, switch its servo power) |
| `figure.py` | the stick figure, worked out from the sheet's lengths |
| `page.py`, `page.html` | the page it draws itself on, answering this computer only |

Its leg and body lengths are the PiDog's published ones: an upper leg of 42 mm, a lower leg of 76 mm, a body 117 by
98 mm. Its neck, head and tail are its own, and so are its angles: they were chosen to draw plainly and are **not**
the PiDog's servo angles, which are measured on the bench (B-12).

    python3 -m wrappers.sim                                              # http://127.0.0.1:8765/
    python3 -m tools.bodycheck wrappers/sim --live --option page=8765    # watch it take the body check

The page's buttons are a hand on the body. None of them is a driver's call: nothing but the body program moves it.
