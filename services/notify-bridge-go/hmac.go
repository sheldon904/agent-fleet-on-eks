package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
)

// signatureHeader carries the hex HMAC-SHA256 of the request body, optionally prefixed
// with "sha256=" (GitHub-webhook style).
const signatureHeader = "X-Signature-256"

// HMACVerifier verifies inbound request signatures against a shared secret.
type HMACVerifier struct {
	secret []byte
}

// NewHMACVerifier returns a verifier bound to secret.
func NewHMACVerifier(secret []byte) *HMACVerifier { return &HMACVerifier{secret: secret} }

// Verify checks that sig equals HMAC-SHA256(body, secret) using a constant-time comparison.
// sig may be bare hex or "sha256=<hex>".
func (v *HMACVerifier) Verify(sig string, body []byte) error {
	if sig == "" {
		return errors.New("missing signature header")
	}
	const prefix = "sha256="
	if len(sig) > len(prefix) && sig[:len(prefix)] == prefix {
		sig = sig[len(prefix):]
	}
	expected := v.Compute(body)
	if !hmac.Equal([]byte(sig), []byte(expected)) {
		return errors.New("signature mismatch")
	}
	return nil
}

// Compute returns the lowercase hex HMAC-SHA256 of body. Exposed so clients and tests can
// produce the same signature the server expects.
func (v *HMACVerifier) Compute(body []byte) string {
	mac := hmac.New(sha256.New, v.secret)
	mac.Write(body)
	return hex.EncodeToString(mac.Sum(nil))
}
