import pandas as pd

from occsol.nomenclature import Regle, classer_brut


def test_regle_brute():
    r = Regle.reference()
    df = pd.DataFrame({
        "code_cs": ["CS1.1.1.1", "CS1.1.2.1", "CS1.1.2.1", "CS2.2.1", "CS2.2.1", "CS2.1.1.1"],
        "code_us": ["US1.1",     "US1.3",     "US2",       "US5",     "US1.1",   "US5"],
    })
    assert classer_brut(df, r).tolist() == [True, False, True, True, False, False]


def test_sans_herbace():
    r = Regle.reference().variante("x", us_herbace_artif=())
    df = pd.DataFrame({"code_cs": ["CS2.2.1"], "code_us": ["US5"]})
    assert not classer_brut(df, r).iloc[0]
