# notes-to-fhir results

| Model | Field F1, all notes | Template notes | Hand-written notes | Patient | Conditions | Medications | Allergies | Observations | Schema-valid replies | Seconds/note |
|---|---|---|---|---|---|---|---|---|---|---|
| `baseline` | **97.4** [95.8–98.7] | 100.0 | 88.7 | 91.9 | 97.2 | 98.6 | 94.3 | 97.3 | 100% | 0.0 |
| `ollama:llama3.2:3b` | **94.0** [92.6–95.3] | 95.5 | 89.4 | 95.7 | 88.4 | 94.9 | 81.6 | 96.0 | 100% | 4.2 |
| `ollama:qwen2.5:3b` | **90.1** [88.0–91.9] | 91.7 | 85.3 | 95.7 | 90.7 | 88.7 | 98.2 | 89.4 | 100% | 4.2 |
| `ollama:gemma3:4b` | **78.8** [77.3–80.3] | 79.2 | 77.6 | 92.9 | 92.2 | 97.0 | 98.8 | 0.0 | 1% | 6.8 |

Traps handled (all notes):

| Model | Skips negated conditions | Skips family history | Marks resolved conditions | Marks stopped drugs | Uses the new dose | Includes drugs started today | Maps brand names | Ignores earlier values | Units (lb, °F, mmol/L) |
|---|---|---|---|---|---|---|---|---|---|
| `baseline` | 38/40 | 51/51 | 18/20 | 15/19 | 22/22 | 28/28 | 34/34 | 11/14 | 63/68 |
| `ollama:llama3.2:3b` | 40/40 | 50/51 | 11/20 | 6/19 | 21/22 | 28/28 | 33/34 | 12/14 | 53/68 |
| `ollama:qwen2.5:3b` | 40/40 | 51/51 | 12/20 | 14/19 | 11/22 | 27/28 | 34/34 | 13/14 | 59/68 |
| `ollama:gemma3:4b` | 40/40 | 51/51 | 8/20 | 2/19 | 20/22 | 28/28 | 32/34 | 0/14 | 0/68 |

Attribute accuracy (matched entities):

| Model | Birth date | Condition status | Dose | Dose unit | Route | Frequency | Drug status | Allergy reaction | Observation value |
|---|---|---|---|---|---|---|---|---|---|
| `baseline` | 94% | 98% | 96% | 96% | 100% | 99% | 97% | 92% | 100% |
| `ollama:llama3.2:3b` | 100% | 91% | 91% | 88% | 94% | 93% | 98% | 100% | 97% |
| `ollama:qwen2.5:3b` | 100% | 94% | 68% | 68% | 89% | 87% | 90% | 100% | 98% |
| `ollama:gemma3:4b` | 97% | 96% | 99% | 100% | 100% | 95% | 100% | 95% | – |
