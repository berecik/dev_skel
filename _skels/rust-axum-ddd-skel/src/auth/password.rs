//! Argon2 password hashing helpers. Kept tiny and dependency-light
//! so the auth module can be tested without spinning up a database.

use argon2::{
    password_hash::{rand_core::OsRng, SaltString},
    Argon2, PasswordHash, PasswordHasher, PasswordVerifier,
};

use crate::shared::DomainError;

/// Hash a password using argon2 with a fresh random salt.
pub fn hash_password(password: &str) -> Result<String, DomainError> {
    let salt = SaltString::generate(&mut OsRng);
    let argon2 = Argon2::default();
    let hash = argon2
        .hash_password(password.as_bytes(), &salt)
        .map_err(|e| DomainError::Password(e.to_string()))?
        .to_string();
    Ok(hash)
}

/// Verify a password against a stored argon2 hash.
pub fn verify_password(password: &str, stored_hash: &str) -> Result<bool, DomainError> {
    let parsed =
        PasswordHash::new(stored_hash).map_err(|e| DomainError::Password(e.to_string()))?;
    Ok(Argon2::default()
        .verify_password(password.as_bytes(), &parsed)
        .is_ok())
}
