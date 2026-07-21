package main

import "testing"

func TestHMACVerify(t *testing.T) {
	v := NewHMACVerifier([]byte("s3cr3t"))
	body := []byte(`{"message":"hi"}`)
	sig := v.Compute(body)

	tests := []struct {
		name    string
		sig     string
		body    []byte
		wantErr bool
	}{
		{"valid bare hex", sig, body, false},
		{"valid with prefix", "sha256=" + sig, body, false},
		{"tampered body", sig, []byte(`{"message":"bye"}`), true},
		{"wrong sig", "deadbeef", body, true},
		{"empty sig", "", body, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := v.Verify(tt.sig, tt.body)
			if (err != nil) != tt.wantErr {
				t.Fatalf("Verify() err = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestHMACDifferentSecret(t *testing.T) {
	body := []byte("payload")
	a := NewHMACVerifier([]byte("key-a"))
	b := NewHMACVerifier([]byte("key-b"))
	if err := b.Verify(a.Compute(body), body); err == nil {
		t.Fatal("expected mismatch across different secrets")
	}
}
