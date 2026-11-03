from services.blueprint_validator import sanitize_content, sanitize_patch

EMBED = "<script src='https://kit.example/form.js'></script>"


def _section(known_text="", **fields):
    return sanitize_content([{"type": 13, **fields}], known_text)[0]


def _patch(action, updates, known_text=""):
    patch = {"action": action, "type": 13, "updates": updates}
    return sanitize_patch(patch, None, known_text)["updates"]


# blueprint
assert _section()["newsletter_provider"] == "serey"
assert _section(newsletter_provider="")["newsletter_provider"] == "serey"
assert _section(newsletter_provider="kit")["newsletter_provider"] == "serey"
assert _section(newsletter_provider="email_octopus")["newsletter_provider"] == "serey"
assert _section(newsletter_provider="kit", kit_embed_script=EMBED)["newsletter_provider"] == "serey"
assert _section(EMBED, newsletter_provider="kit", kit_embed_script=EMBED)["newsletter_provider"] == "kit"
assert _section(EMBED, email_octopus_embed_script=EMBED)["newsletter_provider"] == "email_octopus"

# patches
assert _patch("add_block", {"title": "x"})["newsletter_provider"] == "serey"
assert _patch("add_block", {"newsletter_provider": "kit"})["newsletter_provider"] == "serey"
assert "newsletter_provider" not in _patch("update_block", {"title": "x"})
assert "newsletter_provider" not in _patch("update_block", {"newsletter_provider": "kit"})
assert _patch("update_block", {"newsletter_provider": "serey"})["newsletter_provider"] == "serey"
assert _patch("update_block", {"kit_embed_script": EMBED}, EMBED)["newsletter_provider"] == "kit"

print("ok")
