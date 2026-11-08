# Assets: Handles, Loading, Hot Reload, Lifetime

Scope: how a game refers to something on disk, when it may assume the thing has arrived, and what
keeps it in memory. Asset *content* — the meshes, the audio, the level files — is a content problem;
this chapter is about the handles.

## Contents

- **Handles**
  - BV-ASSET-01 [M] Hold a strong handle exactly as long as the asset is needed
  - BV-ASSET-02 [M] Load once and store the handle, never per frame
  - BV-ASSET-03 [S] Reach for `uuid_handle!` only for a built-in

- **Loading**
  - BV-ASSET-04 [M] Never assume an asset is present the frame after loading it
  - BV-ASSET-05 [M] Handle the failed load, not just the pending one
  - BV-ASSET-06 [S] Gate play on `is_loaded_with_dependencies`, not on the asset alone
  - BV-ASSET-07 [S] Reach for the load builder when a load needs settings
  - BV-ASSET-08 [M] Keep asset paths out of the code that uses them

- **Change and lifetime**
  - BV-ASSET-09 [M] React to `AssetEvent`, not to a per-frame comparison
  - BV-ASSET-10 [S] Keep hot reload working by loading through the server

---

## Handles

### BV-ASSET-01 [M] Hold a strong handle exactly as long as the asset is needed

A strong `Handle<T>` is a reference count: every clone keeps the asset alive, the one in an entity's
component included, and dropping the last one frees it. Keep one wherever the asset is still to be
used, and let it go with what used it: when a level ends, its handle resource goes with it.

**Why:** a handle nothing holds — a discarded preload, an `AssetId` kept in its place — cancels the
load or frees the asset, and the next `load` reads the disk again; one held past its use, in a map
only ever inserted into, is memory no leak detector reports, because nothing leaked.

**Check:** for each `AssetServer::load`, follow the handle: it is stored somewhere that outlives its
use. For each collection of handles, find the removal: a collection with no remove is a cache with
no eviction.

### BV-ASSET-02 [M] Load once and store the handle, never per frame

Load at startup or in `OnEnter`, into one resource per feature — `SpriteHandles`, `LevelAudio`,
`UiFonts` — built with `FromWorld`. Not inside a system that runs every frame.

**Why:** even a cache hit hashes the path, takes a lock and allocates a handle, so a `load` per
frame per entity is measurable, and it hides the real load point. One resource per feature also
makes the loading screen's "is everything here" a walk over one struct.

**Check:** read each `asset_server.load`: one in a system that runs in `Update` or `FixedUpdate` is
a load per frame. Then, for each feature, is there one type holding its handles, or are they built
in more than one system?

```rust
// verified
use bevy::prelude::*;

/// One place the game's sprite handles live, loaded once.
#[derive(Resource, Debug)]
pub struct SpriteHandles {
    pub player: Handle<Image>,
    pub enemy: Handle<Image>,
}

impl FromWorld for SpriteHandles {
    fn from_world(world: &mut World) -> Self {
        Self {
            player: world.load_asset("player.png"),
            enemy: world.load_asset("enemy.png"),
        }
    }
}

#[derive(Debug, Default)]
pub struct SpritesPlugin;

impl Plugin for SpritesPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<SpriteHandles>();
    }
}
```

### BV-ASSET-03 [S] Reach for `uuid_handle!` only for a built-in

`uuid_handle!("…")` builds a `Handle::Uuid` for an asset the engine or a plugin embeds and inserts
itself. Game content goes through the asset server.

**Why:** a UUID handle neither keeps its asset alive nor loads it; it names something another part
of the program is expected to insert. For a texture on disk, that is a handle that never resolves
and an entity that renders nothing.

**Check:** `rg -n 'uuid_handle!' src/` finds each one; each has a matching insertion into
`Assets<T>` in the same crate.

## Loading

### BV-ASSET-04 [M] Never assume an asset is present the frame after loading it

`AssetServer::load` returns immediately with a handle to something that is not there yet. Anything
that must read the asset's contents waits for the load; anything that only passes the handle to the
renderer does not.

**Why:** loading is asynchronous, so `Assets::get` on the next frame returns `None` — except on a
fast machine with a warm cache, which is worse: the bug then appears only on the slow machine or the
cold start.

**Check:** for each `Assets::<T>::get` shortly after a load, ask what the code does when it returns
`None`. "It cannot" is the defect.

### BV-ASSET-05 [M] Handle the failed load, not just the pending one

`LoadState::Failed` is a state a load reaches, and it is where a missing or corrupt file arrives.

**Why:** code that treats everything but `LoadState::Loaded` as "still loading" hangs forever on a
failed load, behind a loading screen with no error. The failure carries the path and the reason,
which turn a bug report that says "it hangs" into one that names the file.

**Check:** for each match on `LoadState`, is there a `Failed` arm that reports? A `_ => {}` catching
it is the hang.

```rust
// verified
use bevy::asset::LoadState;
use bevy::prelude::*;

/// One resource, loaded once, holding the screen's paths (BV-ASSET-02).
#[derive(Resource, Debug)]
pub struct TitleArt {
    pub logo: Handle<Image>,
    pub background: Handle<Image>,
}

impl FromWorld for TitleArt {
    fn from_world(world: &mut World) -> Self {
        Self {
            logo: world.load_asset("ui/logo.png"),
            background: world.load_asset("ui/title.png"),
        }
    }
}

/// Three outcomes, not two. A screen that knows only "arrived" and "not yet"
/// has nowhere to put a file that is never coming, so it waits forever.
#[derive(Resource, Debug, Default, PartialEq, Eq, Reflect)]
#[reflect(Resource)]
pub struct TitleProgress {
    pub ready: usize,
    /// One line per asset that will not arrive: the path, then the reason.
    pub unreachable: Vec<String>,
}

fn poll_title_art(
    assets: Res<AssetServer>,
    art: Res<TitleArt>,
    mut progress: ResMut<TitleProgress>,
) {
    let mut next = TitleProgress::default();
    for handle in [&art.logo, &art.background] {
        match assets.load_state(handle) {
            LoadState::Loaded => next.ready += 1,
            // Both halves of the bug report are in this arm and nowhere
            // else. A `_ => {}` catching it is the difference between "the
            // game hangs on the loading screen" and "ui/logo.png is missing".
            LoadState::Failed(why) => {
                let path = handle.path().map_or_else(String::new, ToString::to_string);
                next.unreachable.push(format!("{path}: {why}"));
            }
            // Naming the two states worth waiting on means a variant added
            // upstream is a compile error rather than a new way to hang.
            LoadState::NotLoaded | LoadState::Loading => {}
        }
    }
    // Recomputed every frame, so `set_if_neq` is what keeps a
    // `resource_changed` gate on the loading screen meaningful.
    progress.set_if_neq(next);
}

#[derive(Debug, Default)]
pub struct TitleArtPlugin;

impl Plugin for TitleArtPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<TitleArt>()
            .init_resource::<TitleProgress>()
            .add_systems(Update, poll_title_art);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bevy::app::TaskPoolPlugin;
    use bevy::asset::AssetPlugin;

    #[test]
    fn a_file_that_is_not_there_is_reported_rather_than_waited_on() {
        let mut app = App::new();
        app.add_plugins((TaskPoolPlugin::default(), AssetPlugin::default()));
        // `ImagePlugin` does this in a real app; its render backend is not
        // part of a headless test.
        app.init_asset::<Image>().add_plugins(TitleArtPlugin);

        for _ in 0..64 {
            app.update();
            if !app
                .world()
                .resource::<TitleProgress>()
                .unreachable
                .is_empty()
            {
                break;
            }
        }

        let progress = app.world().resource::<TitleProgress>();
        assert_eq!(progress.ready, 0);
        assert_eq!(progress.unreachable.len(), 2);
        assert!(
            progress
                .unreachable
                .iter()
                .any(|line| line.starts_with("ui/logo.png: "))
        );
    }
}
```

### BV-ASSET-06 [S] Gate play on `is_loaded_with_dependencies`, not on the asset alone

A scene, a glTF or a material is loaded before its textures are. `is_loaded_with_dependencies` is
what "ready" means, and `RecursiveDependencyLoadState` asks the same question in enum form when the
failure case needs distinguishing.

**Why:** the top-level asset arrives first, so a loading screen that waits for it dismisses itself
while the textures are still arriving, which the player sees as a level that fades in over the first
second of play.

**Check:** for each readiness check, ask whether the asset has dependencies. Meshes, scenes, glTF
and materials all do.

### BV-ASSET-07 [S] Reach for the load builder when a load needs settings

Loader settings, an unapproved path and a guard all go through `AssetServer::load_builder`:
`load_builder().with_settings(…).load(path)`. The variants it replaced are gone.

**Why:** the builder replaced a combinatorial family — `load_*_override`, `load_with_settings`,
`load_with_settings_override` — and is the form upstream extends, so code written against it
survives the next option being added. It also keeps a load with five options readable.

**Check:** `rg -n '\.load_(override|acquire|with_settings)' src/` finds a removed call; the
builder's `with_settings`, `override_unapproved` and `with_guard` replace them.

### BV-ASSET-08 [M] Keep asset paths out of the code that uses them

A path literal appears where the handle is created — a handle resource, a manifest, a content file —
and nowhere else.

**Why:** a path is content, and content moves. A literal in the system that spawns an enemy makes
renaming a file a code change, found by grep, in every system that touched it; paths kept together
can be checked against the disk by a build step.

**Check:** read each string literal ending in a file extension. Each one outside a handle resource,
a content file, or a loader is a path that has escaped.

## Change and lifetime

### BV-ASSET-09 [M] React to `AssetEvent`, not to a per-frame comparison

`AssetEvent::<Image>::Added`, `Modified`, `Removed`, `LoadedWithDependencies`. Not a system that
compares this frame's asset against a cached copy. `Modified` fires only on an actual mutation:
`AssetMut<A>` sets its flag on `DerefMut`, so a `get_mut` that only reads raises nothing. Where the
reaction is per entity — this entity's mesh changed — the filter `AssetChanged<C>` on its handle
component says it with no id-to-entity join, and `Or<(Changed<C>, AssetChanged<C>)>` also catches a
swapped handle.

**Why:** the events are the mechanism the asset server already maintains, so a comparison duplicates
it and gets it wrong in the interesting cases: a modified asset with the same length, an asset
replaced by hot reload between two frames.

**Check:** read for a cached `Handle` or a cached asset value compared each frame. That is an
`AssetEvent` reader, or an `AssetChanged` filter when the answer is per entity.

```rust
// verified
use bevy::prelude::*;

#[derive(Asset, Debug, Default, Reflect)]
pub struct Dialogue {
    pub lines: Vec<String>,
}

/// What the game derives from every `Dialogue` it holds.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct DialogueIndex {
    pub longest: usize,
    /// How many times the index was rebuilt, which on a quiet frame is not
    /// at all. A per-frame comparison could not say that.
    pub rebuilds: usize,
}

/// The asset server already knows what changed, so this reads its answer
/// rather than keeping a copy of every asset and diffing it each frame.
fn reindex(
    mut changes: MessageReader<AssetEvent<Dialogue>>,
    dialogues: Res<Assets<Dialogue>>,
    mut index: ResMut<DialogueIndex>,
) {
    for change in changes.read() {
        match change {
            AssetEvent::Added { .. } | AssetEvent::Modified { .. } | AssetEvent::Removed { .. } => {
                index.longest = dialogues
                    .iter()
                    .map(|(_, dialogue)| dialogue.lines.len())
                    .max()
                    .unwrap_or(0);
                index.rebuilds += 1;
            }
            // A dropped handle and a finished dependency tree change no
            // line of dialogue, so they rebuild nothing.
            AssetEvent::Unused { .. } | AssetEvent::LoadedWithDependencies { .. } => {}
        }
    }
}

#[derive(Debug, Default)]
pub struct DialoguePlugin;

impl Plugin for DialoguePlugin {
    fn build(&self, app: &mut App) {
        app.init_asset::<Dialogue>()
            .init_resource::<DialogueIndex>()
            .add_systems(Update, reindex);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bevy::asset::AssetPlugin;

    #[test]
    fn the_index_is_rebuilt_on_a_change_and_only_on_a_change() {
        let mut app = App::new();
        app.add_plugins((AssetPlugin::default(), DialoguePlugin));

        let handle = app
            .world_mut()
            .resource_mut::<Assets<Dialogue>>()
            .add(Dialogue {
                lines: vec!["hello".to_owned()],
            });
        // The message is written in `PostUpdate` and read on the next frame.
        app.update();
        app.update();
        assert_eq!(app.world().resource::<DialogueIndex>().rebuilds, 1);
        assert_eq!(app.world().resource::<DialogueIndex>().longest, 1);

        // Nothing happened, so nothing is recomputed. A comparison against a
        // cached copy would have walked every asset here.
        app.update();
        assert_eq!(app.world().resource::<DialogueIndex>().rebuilds, 1);

        let mut dialogues = app.world_mut().resource_mut::<Assets<Dialogue>>();
        if let Some(mut dialogue) = dialogues.get_mut(&handle) {
            dialogue.lines.push("goodbye".to_owned());
        }
        app.update();
        app.update();
        assert_eq!(app.world().resource::<DialogueIndex>().rebuilds, 2);
        assert_eq!(app.world().resource::<DialogueIndex>().longest, 2);
    }
}
```

### BV-ASSET-10 [S] Keep hot reload working by loading through the server

Everything loaded through `AssetServer` participates in hot reload. Anything read with `std::fs`
does not. A custom format gets a small `AssetLoader`, half a page that buys the whole mechanism.

**Why:** hot reload is the shortest iteration loop a game has for content, and it is lost one
`fs::read_to_string` at a time — usually for a config or a level file, exactly the content people
most want to edit while the game runs.

**Check:** `rg -n 'std::fs|File::open|include_str!' src/` finds a read past the server; each one of
a file under the asset directory is the finding.
