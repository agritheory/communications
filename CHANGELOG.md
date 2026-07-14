<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# CHANGELOG

<!-- version list -->

## v15.9.0 (2026-07-08)

### Documentation

- Update docs with index and expanded features
  ([`c447fd9`](https://github.com/agritheory/communications/commit/c447fd9b56e929d5c24d9ebbbbc8a23964278cb9))

### Features

- Improve sendmail override setups
  ([`e3ceddc`](https://github.com/agritheory/communications/commit/e3ceddcd39841cbc3e24c9944a03152ee5b72033))


## v15.8.1 (2026-06-16)

### Continuous Integration

- Add assets.json, needed in esig render test
  ([`ab885a9`](https://github.com/agritheory/communications/commit/ab885a9a7313ed64e6acc8a331fe13209a8a212a))

- Install poetry
  ([`deec51e`](https://github.com/agritheory/communications/commit/deec51edb5858c20eeae86795710046c0e5ae80b))

### Documentation

- Add email/portal config
  ([`c867f21`](https://github.com/agritheory/communications/commit/c867f21ce73bfdfbb947b6afd4eabdf38bb0114a))

- Remove client reference, add other config
  ([`e5fc715`](https://github.com/agritheory/communications/commit/e5fc715027ba86c595e89d91a8b52902ec5e33c0))

### Testing

- Add notification document_type to avoid redis cache error
  ([`0b7659c`](https://github.com/agritheory/communications/commit/0b7659cf29f5edaa7d654392db4d737d43eb1738))

- Add patches so code reaches tested except/error log blocks
  ([`8b5b233`](https://github.com/agritheory/communications/commit/8b5b2337b4d32784b35c4947c9b84ae3cba1c8a4))

- Set in_test flag
  ([`512b768`](https://github.com/agritheory/communications/commit/512b7680384e21dbf9337ffcc92cd080d87021ab))

- Use patch for consistent sendmail behavior w or wout smtp setup
  ([`80d742b`](https://github.com/agritheory/communications/commit/80d742b693fa2d05e78652a1855eb554fa406287))


## v15.8.0 (2026-06-12)

### Documentation

- Sliding window notification batching
  ([`c615a0c`](https://github.com/agritheory/communications/commit/c615a0c39401e824321bf18b27388c2291f5bd35))

### Features

- Sendmail override integration
  ([`4a74352`](https://github.com/agritheory/communications/commit/4a74352d2004433bce6699278d206026e7b850c1))


## v15.7.0 (2026-06-07)

### Bug Fixes

- Make fields not required, removed referece to callsites
  ([`c40390f`](https://github.com/agritheory/communications/commit/c40390f2b27c5bf1cfadf174a3684df827f149c9))

### Chores

- Fix mypy error
  ([`cf30ab3`](https://github.com/agritheory/communications/commit/cf30ab3a8b6ea1b8bb1d05994249d2c6b5e09d11))

- Reorganize some files
  ([`8f90b9a`](https://github.com/agritheory/communications/commit/8f90b9a4f2cd16b396a8da69f774776275161e69))

- Update lock file
  ([`2952049`](https://github.com/agritheory/communications/commit/29520491093a0a2324f51681d773bf3c79cb6de6))

### Continuous Integration

- Fix premissions and path
  ([`1cd0214`](https://github.com/agritheory/communications/commit/1cd0214a7fea02a870d3d5b46478dab1a207f860))

- Test cleanup
  ([`eaea8ec`](https://github.com/agritheory/communications/commit/eaea8ecf7b7ee583f777a98fc0350280ef7c9bfc))

### Features

- Add track_overrides
  ([`cff55a7`](https://github.com/agritheory/communications/commit/cff55a79dc1ac6eb63e950c6e7657557f9eb12c4))

### Testing

- Add email override to default fixtures
  ([`7632190`](https://github.com/agritheory/communications/commit/763219066ca3f26bc7813f33e02edbd88bef3c62))


## v15.6.0 (2026-05-09)

### Features

- Enqueue dms
  ([`9559f2c`](https://github.com/agritheory/communications/commit/9559f2c6d02991a148d1790c4d66380fb832f6b8))


## v15.5.0 (2026-04-30)

### Bug Fixes

- Autoname
  ([`df3a13e`](https://github.com/agritheory/communications/commit/df3a13ec2a994be5d9ab5a7b13129c606e358823))

- Layout
  ([`fe4e0a2`](https://github.com/agritheory/communications/commit/fe4e0a2bd797327d281d95c5b7b00b8b6ccdef13))

- Layout
  ([`8b25ec1`](https://github.com/agritheory/communications/commit/8b25ec1596a530a279c57a2286488589e12ced7c))

### Chores

- Rm plans
  ([`e5cae1c`](https://github.com/agritheory/communications/commit/e5cae1caf3c13c2429a7d0bc820881b6239e19e7))

### Features

- Teams notifier via bot network
  ([`49735c6`](https://github.com/agritheory/communications/commit/49735c65ea97133c17bf516e99f4b6a13f927e5d))


## v15.4.0 (2026-04-12)

### Features

- Add query params to calendar for more interactive appointment scheduling
  ([`eeb2646`](https://github.com/agritheory/communications/commit/eeb26469701d40125969848d5ae1515a802e5dc5))


## v15.3.0 (2026-04-08)

### Chores

- Clean up tests
  ([`41ab52a`](https://github.com/agritheory/communications/commit/41ab52a40743aa7b61dd7648b89a5cf11e02ce95))

- Update precommit
  ([`4013dcb`](https://github.com/agritheory/communications/commit/4013dcbcb1fbec7614cbedfb356502fe1e160851))

- Update pyproject and precommit
  ([`5901cfc`](https://github.com/agritheory/communications/commit/5901cfc4ae2abfa6fe5c75ad2ec00810493fe205))

### Documentation

- Update docs
  ([`8437c60`](https://github.com/agritheory/communications/commit/8437c60e1f3ac6c40a3bf653c57d639d8bd72b9c))

### Features

- Calendar timezone bug fixes
  ([`df00e19`](https://github.com/agritheory/communications/commit/df00e19e7ea5a0a813810ed2062110468c5857d5))

- Port public calendar into communciations
  ([`1c25e7f`](https://github.com/agritheory/communications/commit/1c25e7f6440105bb1399404e21f4e40d64a97ee6))


## v15.2.0 (2025-12-19)

### Features

- Make Slack integration respect the "mute_emails" site config
  ([`d528187`](https://github.com/agritheory/communications/commit/d528187845520ca138ade12d0bb8a31e1c3edbd0))


## v15.1.1 (2025-12-19)

### Bug Fixes

- Add slack dependency
  ([`6fe434f`](https://github.com/agritheory/communications/commit/6fe434f01c3078dbbca1d6b579c219a68ec949fc))


## v15.1.0 (2025-09-26)

### Bug Fixes

- Enqueue
  ([`7b12d23`](https://github.com/agritheory/communications/commit/7b12d23e041d62ce67173d25281d4b1ffb115952))

- Last modified notification
  ([`90b22e4`](https://github.com/agritheory/communications/commit/90b22e45103f3ac3680e26e19248cff49aa88abc))

### Features

- Allow configured Notification to be used instead of only email for notify_assignment
  ([`9c251e6`](https://github.com/agritheory/communications/commit/9c251e681c80c2a8044ec523c8f75a256b2b9543))


## v15.0.1 (2025-09-15)

### Bug Fixes

- Override_doctype_class
  ([`e1cf984`](https://github.com/agritheory/communications/commit/e1cf984e095a7b6ea6f426a117dfe92d02eaa707))


## v15.0.0 (2025-09-01)

- Initial Release
