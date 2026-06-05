#!/usr/bin/env gjs
/*
 * GJS runner for the in-tree GoiBench typelib.
 *
 * Run through ./examples/draw-bench/run-gjs-microbench.sh so GI_TYPELIB_PATH
 * and LD_LIBRARY_PATH point at the Meson-built GoiBench-1.0.typelib and
 * libgoibench.so. This intentionally uses system gjs, not the checked-out
 * ./gjs source tree.
 */

imports.gi.versions.GoiBench = '1.0';

const GLib = imports.gi.GLib;
const GoiBench = imports.gi.GoiBench;

function header(title) {
    const version = GLib.getenv('GOI_BENCH_GJS_VERSION') || `gjs ${imports.system.version}`;
    print(`=== ${title} [${version}] ===`);
}

function section(title) {
    print(`--- ${title}`);
}

function timeUsec() {
    return GLib.get_monotonic_time();
}

function bench(name, fn, n = 5_000_000) {
    const warmup = Math.min(Math.floor(n / 100), 50_000);
    for (let i = 0; i < warmup; i++)
        fn();

    const start = timeUsec();
    for (let i = 0; i < n; i++)
        fn();
    const dtUsec = timeUsec() - start;
    const ns = dtUsec * 1000 / n;
    const rate = n / (dtUsec / 1_000_000);
    print(`  ${name.padEnd(36)}  ${ns.toFixed(1).padStart(7)} ns/call   ${(rate / 1e6).toFixed(2).padStart(6)} M/s`);
}

function benchInner(name, fn, outer, inner) {
    const warmup = Math.min(Math.floor(outer / 10), 10_000);
    for (let i = 0; i < warmup; i++)
        fn();

    const start = timeUsec();
    for (let i = 0; i < outer; i++)
        fn();
    const dtUsec = timeUsec() - start;
    const calls = outer * inner;
    const ns = dtUsec * 1000 / calls;
    const rate = calls / (dtUsec / 1_000_000);
    print(`  ${name.padEnd(36)}  ${ns.toFixed(1).padStart(7)} ns/call   ${(rate / 1e6).toFixed(2).padStart(6)} M/s`);
}

function main() {
    header('gjs_microbench');

    section('free functions');
    const nv = GoiBench.noop_void;
    bench('noop_void   (0 args, void)', () => nv());
    const ni = GoiBench.noop_int;
    bench('noop_int    (0 args, int)', () => ni());
    const f1 = GoiBench.in_1_int;
    bench('in_1_int    (1 arg)', () => f1(42));
    const f2 = GoiBench.in_2_int;
    bench('in_2_int    (2 args)', () => f2(1, 2));
    const f3 = GoiBench.in_3_int;
    bench('in_3_int    (3 args)', () => f3(1, 2, 3));
    const f4 = GoiBench.in_4_int;
    bench('in_4_int    (4 args)', () => f4(1, 2, 3, 4));
    const f5 = GoiBench.in_5_int;
    bench('in_5_int    (5 args)', () => f5(1, 2, 3, 4, 5));
    const f6 = GoiBench.in_6_int;
    bench('in_6_int    (6 args)', () => f6(1, 2, 3, 4, 5, 6));
    const fm = GoiBench.in_5_mixed;
    bench('in_5_mixed  (i32,i64,f64,i32,u32)', () => fm(1, 2, 3.0, 4, 5));

    if (typeof GoiBench.callback_no_args_loop === 'function') {
        section('direct callbacks (C loop)');
        const inner = 10_000;
        const outer = 1_000;
        const cb0 = GoiBench.callback_no_args_loop;
        const cbi = GoiBench.callback_int_loop;
        const cbo = GoiBench.callback_out_int_loop;
        const cbm = GoiBench.callback_mixed_loop;
        const cbu = GoiBench.callback_user_data_loop;

        benchInner('callback no args', () => cb0(() => {}, inner), outer, inner);
        benchInner('callback int -> int', () => cbi(() => 1, inner), outer, inner);
        benchInner('callback int -> out int', () => cbo(() => 1, inner), outer, inner);
        benchInner('callback mixed -> int', () => cbm(() => 1, inner), outer, inner);
        /*
         * GJS hides the annotated closure user_data parameter from the JS call
         * signature, so the comparable row is the closure-slot shape, not
         * goi's explicit Python user_data value path.
         */
        benchInner('callback closure slot', () => cbu(() => 1, inner), outer, inner);
    }

    if (typeof GoiBench.Object !== 'function') {
        print('');
        print('  SKIP rest: GoiBench.Object not present - rebuild the bench typelib');
        return;
    }

    section('methods on GObject (bound)');
    const obj = GoiBench.Object.new();
    const other = GoiBench.Object.new();

    const setFlag = obj.set_flag.bind(obj);
    const setLabel = obj.set_label.bind(obj);
    const getLabel = obj.get_label.bind(obj);
    const getIndex = obj.get_index.bind(obj);
    const lookup = obj.lookup.bind(obj);
    const nth = obj.nth.bind(obj);
    const indexOf = obj.index_of.bind(obj);

    bench('set_flag(self, bool)', () => setFlag(true));
    bench('set_label(self, str)', () => setLabel('hi'));
    bench('set_label(self, null)', () => setLabel(null));
    bench('get_label(self) -> str', () => getLabel());
    bench('get_index(self) -> int', () => getIndex());
    bench('lookup(self, str) -> GO', () => lookup('undo'));
    bench('nth(self, int) -> GO', () => nth(0));
    bench('index_of(self, GO)->int', () => indexOf(other));

    section('methods on GObject (attr-each-call)');
    bench('set_flag attr-each', () => obj.set_flag(true));
    bench('lookup attr-each', () => obj.lookup('undo'));

    section('signal emit (GClosure)');
    obj.connect('tick', () => {});
    bench('emit tick (JS listener)', () => obj.tick(), 1_000_000);

    const bare = GoiBench.Object.new();
    bench('emit tick (no listener)', () => bare.tick(), 1_000_000);
}

main();
