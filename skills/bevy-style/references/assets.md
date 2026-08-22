# Assets: Handles, Loading, Hot Reload, Lifetime

Scope: how a game refers to something on disk, when it may assume the thing has arrived, and what
keeps it in memory. Asset *content* — the meshes, the audio, the level files — is a content problem;
this chapter is about the handles.

## Contents

- **Handles**
  - BV-ASS-01 [M] Treat a handle as a reference count, not a path
  - BV-ASS-02 [M] Load once and store the handle, never per frame
  - BV-ASS-03 [S] Keep the handles for a feature in one resource
  - BV-ASS-04 [M] Wrap a handle in a named component (see BV-ECS-14)
  - BV-ASS-05 [S] Reach for the `weak_handle!` macro only for a built-in

- **Loading**
  - BV-ASS-06 [M] Never assume an asset is present the frame after loading it
  - BV-ASS-07 [M] Handle the failed load, not just the pending one
  - BV-ASS-08 [S] Gate play on `is_loaded_with_dependencies`, not on the asset alone
  - BV-ASS-09 [S] Reach for the load builder when a load needs settings
  - BV-ASS-10 [M] Keep asset paths out of the code that uses them

- **Change and lifetime**
  - BV-ASS-11 [M] React to `AssetEvent`, not to a per-frame comparison
  - BV-ASS-12 [M] Do not take `ResMut<Assets<T>>` to read
  - BV-ASS-13 [S] Keep hot reload working by loading through the server
  - BV-ASS-14 [M] Do not hold a strong handle to something the game has finished with

---

## Handles

### BV-ASS-01 [M] Treat a handle as a reference count, not a path

A `Handle<T>` keeps the asset alive. Dropping the last one unloads it.

**Why:** this is the property that surprises people: a handle stored in a local, used to spawn, and
then dropped can unload the asset out from under the entity that is still using it — and the symptom
is a missing texture rather than an error. The reverse also matters: a handle kept in a resource
forever keeps its asset in memory forever, which is how a game ends up with every level loaded at
once.

**Check:** for each `AssetServer::load`, follow the handle. If it is not stored anywhere that
outlives its use, the asset can be dropped.

### BV-ASS-02 [M] Load once and store the handle, never per frame

`AssetServer::load` in a startup or `OnEnter` system, stored in a resource. Not inside a system that
runs every frame.

**Why:** `load` is cheap on a cache hit and is not free — it hashes the path, takes a lock, and
allocates a handle — so calling it per frame per entity is measurable. Worse, it reads as a load,
which makes the code look like it is doing something it is not, and it hides the actual load point
from anyone trying to find out when an asset arrives.

**Check:** grep for `asset_server.load` inside `Update` or `FixedUpdate` systems.

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
        let assets = world.resource::<AssetServer>();
        Self {
            player: assets.load("player.png"),
            enemy: assets.load("enemy.png"),
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

### BV-ASS-03 [S] Keep the handles for a feature in one resource

`SpriteHandles`, `LevelAudio`, `UiFonts` — one resource per feature, built with `FromWorld`.

**Why:** it gives the feature one place where every path appears, which is what makes an asset
audit possible, and it makes the loading state's "is everything here" check a matter of iterating
one struct. Scattering handles across the systems that use them means nothing can answer "what does
this feature need on disk".

**Check:** for each feature, is there a single type holding its handles? If handles are constructed
in more than one system, they are scattered.

### BV-ASS-04 [M] Wrap a handle in a named component (see BV-ECS-14)

Owned by `references/ecs.md` BV-ECS-14. An entity may want two handles of the same asset type, so
the component type has to be the meaning rather than the asset kind.

### BV-ASS-05 [S] Reach for the `weak_handle!` macro only for a built-in

`weak_handle!("…")` is for an asset the engine or a plugin embeds and registers itself. Game content
goes through the asset server.

**Why:** a weak handle does not keep the asset alive and does not cause it to load — it names
something that is expected to be inserted by something else. That is exactly right for a shader a
plugin adds at startup and exactly wrong for a texture on disk, where the result is a handle that
never resolves and an entity that renders nothing.

**Check:** grep for `weak_handle!`. Each occurrence should have a matching insertion into
`Assets<T>` in the same crate.

## Loading

### BV-ASS-06 [M] Never assume an asset is present the frame after loading it

`AssetServer::load` returns immediately with a handle to something that is not there yet.

**Why:** loading is asynchronous, so `Assets::get` on the next frame returns `None` — and on a fast
machine with a warm cache it sometimes returns the asset, which is worse, because the bug only
appears on the slow machine or the cold start. Anything that must read the asset's contents waits
for the load; anything that only passes the handle to the renderer does not.

**Check:** for each `Assets::<T>::get` shortly after a load, ask what the code does when it returns
`None`. "It cannot" is the defect.

### BV-ASS-07 [M] Handle the failed load, not just the pending one

`LoadState::Failed` is a state a load reaches, and it is where a missing or corrupt file arrives.

**Why:** code that waits for `LoadState::Loaded` and treats everything else as "still loading" hangs
forever on a failed load, showing a loading screen with no error. The path and the reason are both
in the failure; surfacing them is the difference between a bug report that says "it hangs" and one
that names the file.

**Check:** for each match on `LoadState`, is there a `Failed` arm that reports? A `_ => {}` catching
it is the hang.

### BV-ASS-08 [S] Gate play on `is_loaded_with_dependencies`, not on the asset alone

A scene, a glTF or a material is loaded before its textures are. `is_loaded_with_dependencies` is
what "ready" means.

**Why:** the top-level asset arrives first, so a loading screen that waits for it dismisses itself
while the textures are still arriving — which the player sees as a level that fades in over the
first second of play. `RecursiveDependencyLoadState` is the same question in enum form when the
failure case needs distinguishing.

**Check:** for each readiness check, ask whether the asset has dependencies. Meshes, scenes, glTF
and materials all do.

### BV-ASS-09 [S] Reach for the load builder when a load needs settings

0.19 exposes the advanced load variants through `AssetServer::load_builder`. Use it rather than
reaching for `load_with_settings` plus a chain of overrides.

**Why:** the builder is the form upstream will keep extending — the variants it replaced were a
combinatorial family of `load_*_override`, `load_with_settings`, `load_with_settings_override` — so
code written against the builder survives the next variant being added. It also keeps a load with
five options readable.

**Check:** grep for `load_with_settings` and `load_override`. Each is a builder call in the old
spelling.

### BV-ASS-10 [M] Keep asset paths out of the code that uses them

A path literal appears where the handle is created — a handle resource, a manifest, a content file
— and nowhere else.

**Why:** a path is content, and content moves. A literal in the system that spawns an enemy means
renaming a file is a code change, found by grep, in every system that touched it. Keeping the paths
together also makes the set auditable against what is actually on disk, which a build step can then
check.

**Check:** grep for string literals ending in a file extension. Each one outside a handle resource,
a content file, or a loader is a path that has escaped.

## Change and lifetime

### BV-ASS-11 [M] React to `AssetEvent`, not to a per-frame comparison

`AssetEvent::<Image>::Added`, `Modified`, `Removed`, `LoadedWithDependencies`. Not a system that
compares this frame's asset against a cached copy.

**Why:** the events are the mechanism the asset server already maintains, so a comparison duplicates
it and gets it wrong in the interesting cases — a modified asset with the same length, an asset
replaced by hot reload between two frames. In 0.19 `Modified` fires only on an actual mutation,
which removed the last reason people had for not trusting it.

**Check:** grep for a cached `Handle` or a cached asset value compared each frame. That is an
`AssetEvent` reader.

### BV-ASS-12 [M] Do not take `ResMut<Assets<T>>` to read

`Res<Assets<T>>` and `get`. `ResMut` only where the system inserts or mutates an asset.

**Why:** it is BV-STA-07 with a resource everything touches: `Assets<Image>` is read by the render
extraction, by UI, by sprites and by anything else showing a texture, so a system holding it mutably
to read serialises against all of them for as long as it runs. The change-detection half is no
longer a hazard — 0.19's `AssetMut<A>` sets its flag on `DerefMut`, so a `get_mut` that only reads
raises nothing — which leaves the scheduling cost as the whole of the reason, and it is enough.

**Check:** for each `ResMut<Assets<`, find the mutation. A system that only calls `get` wants `Res`.

### BV-ASS-13 [S] Keep hot reload working by loading through the server

Everything loaded through `AssetServer` participates in hot reload. Anything read with `std::fs`
does not.

**Why:** hot reload is the shortest iteration loop a game has for content, and it is lost one
`fs::read_to_string` at a time — usually for a config or a level file, which is exactly the content
people most want to edit while the game runs. Writing a small `AssetLoader` for a custom format is
half a page and buys the whole mechanism.

**Check:** grep for `std::fs`, `File::open` and `include_str!` on anything under the asset
directory.

### BV-ASS-14 [M] Do not hold a strong handle to something the game has finished with

When a level ends, its handle resource goes with it. A handle held in a resource that outlives the
level keeps the level in memory.

**Why:** handles are the only thing keeping an asset loaded, so an accumulating collection of them
is an accumulating memory footprint with no other symptom — no leak detector fires, because nothing
leaked. The usual shape is a `HashMap<String, Handle<Image>>` that is only ever inserted into.

**Check:** for each collection of handles, find the removal. A collection with no remove is a cache
with no eviction.
