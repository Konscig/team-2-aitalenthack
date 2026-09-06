import pandas as pd
from src.favourability30_visual_comparison import RULES,apply_fixed_rules

def test_five_rules_are_exactly_fixed():
    assert len(RULES)==5
    assert RULES[0]=={"rule":"RULE_1_STRICT","F":.90,"A":.002,"R":.002}
    assert RULES[-1]=={"rule":"RULE_5_BROAD","F":.80,"A":None,"R":.010}

def test_signal_columns_ignore_actual_regret():
    frame=pd.DataFrame({"favourability_percentile_30":[.95,.82],"past_advantage_5":[.01,-.01],"predicted_regret_5":[.001,.009],"actual_regret_5":[1.,0.]})
    before=apply_fixed_rules(frame).filter(like="signal_rule");frame.actual_regret_5=[0.,1.]
    assert before.equals(apply_fixed_rules(frame).filter(like="signal_rule"))
