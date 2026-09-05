include!(concat!(env!("OUT_DIR"), "/generated.rs"));
unsafe extern "C" {
    fn native_answer() -> i32;
}
fn main() {
    assert_eq!(macro_probe::identity!(unsafe { native_answer() }), EXPECTED);
}
#[test]
fn native_and_macro() {
    main();
}
