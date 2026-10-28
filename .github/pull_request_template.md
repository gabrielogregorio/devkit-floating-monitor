## What changes

<!-- one or two lines: what the user notices -->

## Changelog

[...autoGenerate]

## Checklist

- [ ] `VERSION` bumped (merging into `main` creates the tag `vX.Y.Z` and the release)
- [ ] `./run-tests.sh` ends with `ALL GREEN`
- [ ] New menu or tray text is English inside `tr()` with its line in `PT_BR` in `i18n.py`
- [ ] Still no new dependency: standard library + `gi` (Gtk/Gdk/GLib 3.0), no cairo, no subprocess in the tick
- [ ] New config key added to `DEFAULTS` (the user's file is merged, never rewritten from scratch)
- [ ] Tested on a real GNOME X11 session: the line shows, drags, the menu and the top bar icon work
