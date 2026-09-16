import json
import pytest
from FormalLLM.llm.parser import parse_llm_response
from FormalLLM.lspec.ast import BinaryOp, Variable, Number

def test_parse_strengthen_post():
    response = json.dumps({"law": "strengthen_post", "parameters": {"intermediate_post": "x >= 0"}})
    law, params = parse_llm_response(response)
    assert law == "strengthen_post"
    assert "intermediate_post" in params
    assert isinstance(params["intermediate_post"], BinaryOp)

def test_parse_weaken_pre():
    response = json.dumps({"law": "weaken_pre", "parameters": {"intermediate_pre": "x >= 0"}})
    law, params = parse_llm_response(response)
    assert law == "weaken_pre"
    assert "intermediate_pre" in params

def test_parse_initialized_skip():
    response = json.dumps({"law": "initialized_skip", "parameters": {}})
    law, params = parse_llm_response(response)
    assert law == "initialized_skip"
    assert params == {}

def test_parse_flexible_sequential():
    response = json.dumps({"law": "flexible_sequential", "parameters": {
        "pre1": "x >= 0",
        "post1": "x >= 0",
        "pre2": "x >= 0",
        "post2": "x >= 0"
    }})
    law, params = parse_llm_response(response)
    assert law == "flexible_sequential"
    assert all(k in params for k in ("pre1", "post1", "pre2", "post2"))

def test_parse_unknown_law_still_raises():
    response = json.dumps({"law": "teleportation", "parameters": {}})
    with pytest.raises(ValueError, match="Unknown law"):
        parse_llm_response(response)
