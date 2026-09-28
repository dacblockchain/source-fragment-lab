# A verifiable draw (`source-fragment-lab/draw/v1`)

Suppose you run a giveaway and want anyone to be able to check that the winners were not chosen by hand. A Source Fragment helps, but it cannot do this alone: you hold the bytes, so you know them before anyone else. If you knew the random value while entries were still open, you could add fake entries until your friend won.

The fix is to combine two values that nobody knows in advance:

| Value | Who can't predict it |
|---|---|
| A fragment chunk, committed by hash before entries close | Participants and block producers: they never see the chunk until you reveal it |
| The hash of a DAC mainnet block mined **after** entries close, and confirmed | You: the block does not exist yet when the entry list is frozen |

## Procedure

1. **Announce** before entries close:
   - the chunk you will use: fragment file, chunk index `i`, and `SHA-256(chunk_i)`;
   - the block height `H` whose hash will be mixed in, far enough ahead that it is mined after the close;
   - the number of winners `k`.
2. **Close entries, before block `H` is mined.** Publish the entry list and its `entries_hash`. One entry per line, trimmed, empty lines dropped, order as published. A list that first appears after block `H` could have been arranged to fit the outcome, so it does not count.
3. **Wait** for block `H` plus 12 confirmations (about a minute on DAC's 5-second blocks). The tools refuse a hash with fewer confirmations, because a block that can still be reorganised away is a block someone could replace.
4. **Reveal** the chunk (hex) and run the draw. Publish the transcript.

Anyone can then check that `SHA-256(chunk)` matches the announcement, fetch block `H` themselves, and re-run the draw.

## Computation

```
entries_hash = SHA-256( UTF-8( entries joined with "\n" ) )     (32 raw bytes)
block(b)     = HKDF-SHA256( ikm  = chunk_i            (2,048 bytes),
                            salt = block_hash_H        (32 bytes),
                            info = "source-fragment-lab/draw/v1" ‖ entries_hash ‖ uint32be(b),
                            L    = 8160 )
seed_stream  = block(0) ‖ block(1) ‖ …   (only as many blocks as the draw reads)
winners      = the entries picked by the first k steps of a Fisher–Yates
               shuffle, driven by integers read from seed_stream
```

With `n` entries and `1 ≤ k ≤ n` winners, step `s = 0 … k-1` sets `j = n-1-s`, picks `r = randbelow(j + 1)`, swaps entries `j` and `r`, and takes entry `j` as winner number `s + 1`. Duplicate entries are refused: one line is one ticket, so a name that appears twice must be made unique by the organizer before the list is published. Integers are read from the stream with the rejection sampling defined in [mixing.md](mixing.md#uniform-numbers-without-bias).

## What this does not protect against

- **Choosing the chunk after the fact.** Prevented by publishing the chunk hash first. The tools require the announced commitment and refuse to run without it.
- **Arranging the entries after the fact.** Prevented only if the list and its hash are public before block `H`. The tools cannot check when you published it; your audience can.
- **Withholding the result.** You could refuse to reveal an outcome you dislike. Publish the commitment publicly and in advance so that a missing reveal is visible to everyone.
- **A block producer who is also the organizer.** They could withhold block `H`, or reorganise it away before it is confirmed, and try again. Waiting for confirmations raises the cost, and on a network with many independent validators it is expensive, but it is not impossible.
