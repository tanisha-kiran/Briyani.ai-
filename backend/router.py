"""Semantic visual routing for local lesson planning.

Rules are only decisive for an unambiguous match. Ambiguous and multi-part
questions are classified by the local Ollama model with an enum-only schema;
the pipeline still has a safe explain fallback when that small request fails.
"""
from dataclasses import dataclass
import json
import re

@dataclass(frozen=True)
class Archetype:
    id: str
    description: str
    patterns: tuple[str,...]
    visual_instruction: str

REGISTRY={
    'comparison': Archetype('comparison','Compare two related ideas, systems, or alternatives.',(r'\bvs\.?\b',r'\bversus\b',r'\bdifference between\b',r'\bcompare\b'),'Use a side-by-side comparison when two alternatives are central; name the same criteria on both sides.'),
    'process': Archetype('process','Explain a sequence, mechanism, cycle, or transformation.',(r'\bhow does\b',r'\bprocess\b',r'\bcycle\b',r'\bstages?\b',r'\bsteps?\b'),'Use a directional flow or a cycle. Every arrow must state the relationship or transformation.'),
    'math': Archetype('math','Explain a mathematical relationship, proof, calculation, or graph.',(r'\b(theorem|equation|derivative|integral|matrix|fraction|quadratic|pythagorean)\b',r'\bcalculate\b'),'Use an equation, geometric transformation, or graph with labeled quantities; walk through one compact worked example.'),
    'code': Archetype('code','Explain programming concepts, algorithms, or execution.',(r'\b(python|javascript|java|sql|algorithm|binary search|sorting|loop|function|database)\b',r'```'),'Use a short display-only code trace or state diagram; never execute model-supplied code.'),
    'timeline': Archetype('timeline','Explain historical events, chronological change, or development over time.',(r'\b(history|historical|timeline|century|war|revolution|evolution)\b',r'\bwhen did\b'),'Use a chronological timeline with dated milestones only when dates are known from the lesson context.'),
    'system': Archetype('system','Explain parts of a scientific system, geography, or a conceptual mechanism.',(r'\b(solar system|plate tectonics|gravity|earthquake|neural network|ecosystem)\b',),'Use a labeled diagram and one small motion only when it directly demonstrates the mechanism.'),
    'explain': Archetype('explain','Explain a general educational concept clearly.',(), 'Start with the core idea, then use the clearest diagram or process visual for the mechanism.'),
}

def rule_scores(question: str) -> dict[str,int]:
    text=question.lower().strip()
    return {item.id:sum(bool(re.search(pattern,text)) for pattern in item.patterns) for item in REGISTRY.values() if item.patterns}

def route(question: str, local_llm) -> tuple[str,float]:
    scores=rule_scores(question)
    ranked=sorted(scores.items(),key=lambda pair:pair[1],reverse=True)
    if ranked and ranked[0][1] and (len(ranked)==1 or ranked[1][1]==0):
        return ranked[0][0],.9
    schema={'type':'object','properties':{'archetype':{'type':'string','enum':list(REGISTRY)}},'required':['archetype'],'additionalProperties':False}
    menu={item.id:item.description for item in REGISTRY.values()}
    try:
        answer=json.loads(local_llm('Classify this educational question. Choose one visual teaching archetype. Return only the constrained JSON object. Options: '+json.dumps(menu)+' Question: '+question,schema))
        selected=answer.get('archetype')
        if selected in REGISTRY:return selected,.7
    except Exception:
        pass
    return 'explain',.3