use enigo::{Enigo, Keyboard, Settings, Direction, Key};
use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize)]
struct Command {
    action: String,
    text: Option<String>,
}

fn main() {

    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();

    let cmd: Command = serde_json::from_str(&input).unwrap();

    let mut enigo = Enigo::new(&Settings::default()).unwrap();

    match cmd.action.as_str() {

        "type" => {
            if let Some(text) = cmd.text {
                enigo.text(&text);
            }
        }

        "enter" => {
            enigo.key(Key::Return, Direction::Click);
        }

        _ => {}
    }
}