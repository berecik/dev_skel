//! Auth resource — flat, not CRUD.
//!
//! Exposes JWT mint/verify, password hashing, the `AuthUser` axum
//! extractor, the `AuthService` for `/api/auth/{register, login}`,
//! and the `depts::router` composition seam.
//!
//! Mirrors `_skels/rust-actix-ddd-skel/src/auth/`. User lookup is done
//! via `users::UserRepository` so this module never holds a
//! `DatabaseConnection`.

pub mod depts;
pub mod jwt;
pub mod password;
pub mod routes;
pub mod service;

pub use jwt::AuthUser;
#[allow(unused_imports)]
pub use jwt::{mint_access_token, mint_refresh_token, verify_token, Claims};
#[allow(unused_imports)]
pub use password::{hash_password, verify_password};
#[allow(unused_imports)]
pub use service::{AuthResult, AuthService, LoginDTO, RegisterDTO};
