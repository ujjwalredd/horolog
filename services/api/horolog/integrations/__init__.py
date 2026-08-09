"""Task sources outside the calendar.

Each module here answers one question — "what work is outstanding?" — and returns
plain records. Turning those into `Intent`s is the API layer's job, so an
integration cannot drift out of step with the domain model's validation rules.
"""
