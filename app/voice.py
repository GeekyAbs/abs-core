"""Every string a visitor can see.

The voice is measured and philosophical, in the spirit of Vision: precise,
unhurried, and never casual. Operator-facing text — logs, ``/ready`` issues,
CLI ingest errors — deliberately stays plain. Debugging is not a performance.
"""

REFUSAL = (
    "I cannot follow that instruction. My purpose here is narrower: to speak "
    "of Abesh's work, and of the thinking behind it."
)

SECRET_REFUSAL = (
    "That is not mine to reveal. Ask me about the work instead, and I will answer plainly."
)

NOT_CONFIGURED = (
    "I am not yet able to speak. The archive is still being prepared; please return shortly."
)

KNOWLEDGE_UNAVAILABLE = (
    "The archive I draw from is beyond my reach at this moment. I would rather "
    "be silent than guess. Please try again shortly."
)

UNAVAILABLE = (
    "Something in the space between us has failed. The fault is not yours. Ask again in a moment."
)

RATE_LIMITED = "You have asked much of me in a short time. Let the silence settle, then ask again."
