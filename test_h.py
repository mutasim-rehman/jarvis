import sys
import os
sys.path.append(os.getcwd())
from backend.app.heuristics import classify_user_text, reconcile_llm_intent

queries = [
    'play the song "duur" by strings',
    'play song by "the handsome family"',
    'play a song by "the handsome family"',
    'play the song duur by strings',
    'play watch out by 2 chainz',
    'watch artificial intelligence tutorial on youtube'
]

for q in queries:
    cls = classify_user_text(q)
    intent = cls.force_intent or 'UNKNOWN'
    target = cls.force_target
    intent, target = reconcile_llm_intent(q, intent, target)
    print(f'{q!r} -> intent={intent}, target={target}')
