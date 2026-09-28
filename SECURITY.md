# Security

## Threat model, in plain words

| Who | What they know | What protects you |
|---|---|---|
| **Interstellar's operator** | Every byte of your fragment: it stored them before delivery | Mixing with your own OS randomness (`HKDF(os_random ‖ fragment)`). Without your local half, the operator cannot rebuild any key |
| **Your OS random generator** | Its own output, if it is weak or compromised | The quantum half of the mix |
| **Anyone who gets your `.bin` file** | The same as the operator | The same mixing. Keep the file private anyway, and delete it once it is used up |
| **A draw organizer** | Their own chunk, before anyone else | The published commitment, plus a block hash mined after entries close ([docs/draw.md](docs/draw.md)) |

What a Source Fragment gives you is **provenance**: the proof shows that the bytes come from a reservoir sealed and anchored on DAC mainnet before they were assigned to you. It does not give you secrecy on its own. That is what the mixing is for.

## Things these examples deliberately do not do

- **One-time pads.** A one-time pad made from fragment bytes is only as secret as the fragment, and the operator has seen it.
- **Keys from the fragment alone.** No example offers this, not even behind a flag.
- **Custom cryptography for real use.** `fragmentlab encrypt` is a readable example of the STREAM construction on AES-256-GCM. For real files, generate an identity with `fragmentlab keys age` and encrypt with [age](https://age-encryption.org).

## Reporting a problem

Please do not open a public issue for a vulnerability. Email **security@dachain.tech** with the details, and we will reply within a few working days.
