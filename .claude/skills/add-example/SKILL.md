---
name: add-example
description: Add a runnable example bot to examples/ demonstrating a feature, matching examples/simple_menu.py style. Use when the user says "add an example" or "demo this feature".
---

# Add an example

Add a runnable example bot under `examples/` that demonstrates one feature, following
the style of the existing examples.

## Reference

Read `examples/simple_menu.py` and `examples/conversation_handler_menu.py` first and
mirror their structure.

## Steps

1. **Create `examples/<feature>_menu.py`** with a module docstring describing what the
   example shows. Follow the existing pattern:
   - `logging.basicConfig(...)` + module logger.
   - A module-level `router = MenuRouter()`.
   - A `/start` `CommandHandler` that builds a menu with `MenuBuilder(...)...build()` and
     replies with `reply_markup=menu`.
   - `@router.handler("name")` async handlers with the
     `(update, context, params)` signature that `edit_message_text` / `answer`.
   - A `main()` that builds the `Application`, reads the token from the environment
     (`os.environ["BOT_TOKEN"]` or `os.environ.get(...)`) rather than hardcoding, adds
     `CommandHandler("start", start)` and `CallbackQueryHandler(router.route)`, and calls
     `application.run_polling(allowed_updates=Update.ALL_TYPES)`.
   - `if __name__ == "__main__": main()` so it runs via
     `python examples/<feature>_menu.py`.
2. **Keep it lint-clean**: 100-char lines, double quotes, ruff + black clean. Examples
   are excluded from bandit but should still pass `ruff check`/`black`.
3. **Link it**: add the example to the README "Examples" section and to the relevant
   docs page (e.g. a guide that the feature belongs to).
4. **Verify it parses**: `python -m py_compile examples/<feature>_menu.py` (and
   `black --check examples` / `ruff check examples`). A full bot run needs a real token,
   so a parse/lint check is sufficient.

## Output

List the files created/edited (the example plus README/docs links).
