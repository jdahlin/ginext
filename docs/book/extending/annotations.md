# Introspection annotations

> The gtk-doc comments above each function tell introspection how to call it from another language. Get them wrong and Python crashes; get them right and the binding is free.

## What this chapter covers

- The comment format: a gtk-doc block immediately before each public function.
- The annotations that matter most:
    - **`(transfer none|full|container)`** on parameters and return values.
    - **`(nullable)`** vs nothing — goi refuses NULL by default.
    - **`(out)`**, **`(out caller-allocates)`**, **`(inout)`**.
    - **`(array length=...)`**, **`(array zero-terminated=1)`**, **`(array fixed-size=N)`**.
    - **`(element-type ...)`** on GList/GHashTable.
    - **`(scope call|async|notified|forever)`** on callback parameters.
    - **`(closure ...)`** linking the user-data argument to its callback.
    - **`(destroy ...)`** linking the destroy notify to its callback.
    - **`(constructor)`** on constructor methods.
    - **`(skip)`** to hide from introspection entirely.
- Property annotations on `GParamSpec` (most are derived automatically, but `(nullable)` matters).
- Signal annotations.
- A debugging workflow when "Python crashes calling my function":
    1. Check transfer.
    2. Check nullable.
    3. Check array length annotations.
    4. Re-run `g-ir-scanner` and inspect the `.goi` XML.
- Validating annotations with `g-ir-doc-tool` and runtime tests.

## What you'll be able to do

- Annotate every public function correctly the first time.
- Debug introspection-related crashes from the symptom.

## Notes for the writer

- This is the most error-prone area of writing GObject libraries. Make examples ironclad.
- A "common annotation mistakes" appendix is the most reused artifact.
