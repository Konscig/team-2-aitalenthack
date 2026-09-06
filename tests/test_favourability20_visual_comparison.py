import pandas as pd
from src.favourability20_visual_comparison import RULES,apply_rules

def test_same_five_fixed_rules_are_reused():
    assert len(RULES)==5 and RULES[0]["rule"]=="RULE_1_STRICT" and RULES[-1]["rule"]=="RULE_5_BROAD"

def test_20_signal_does_not_depend_on_actual_regret():
    frame=pd.DataFrame({"favourability_percentile_20":[.95,.5],"past_advantage_5":[.01,-.01],"predicted_regret_5":[.001,.02],"actual_regret_5":[1.,0.]})
    before=apply_rules(frame).filter(like="signal_rule");frame.actual_regret_5=[0.,1.]
    assert before.equals(apply_rules(frame).filter(like="signal_rule"))
