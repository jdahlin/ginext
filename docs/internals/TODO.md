cleanups
- general overview, avoid duplication
- move boolean special handling to the right abstraction layer
- remove pygir/_core directory structure
- move things into types/
- merge things in types/

override
- finish and test for gtk.idle add
- port over all from pygtk
- port over all from gstreamer

features
- require()
- gil vs nogil
- run complete tests from pygobject
- run tests in valgrind
- heavy tox usage
- measure code coverage and tests
- generate type stubs
- typos (did you mean icon_name="xxx" instead of Gtk.Button(stock="xxx"))
- investigate JIT how much it will help
- signals auto truncate

examples
- hello world (done)
- drawing (done)
- text-editor fully featured (done)
- video player (showtime in progress, nvidia driver issues)
- pitivi (glycin rgb8 errors)
- port gtk-demo
- port gtk-widgetfactory
- file manager
- terminal (vt)
- web browser (webkit)
- agent chat + code ux
- simple obsidian?
- nice free threading io and cpu in many threads

docs
- api: write generator
- widget gallery
- explain internals in .md files
- acknowledgements


