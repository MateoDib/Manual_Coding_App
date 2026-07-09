# Coding Protocol

## Purpose

The coding protocol translates qualitative interview responses into compact, DAG-compatible topic sequences. The objective is not only to identify themes, but also to preserve the structure of participants' reasoning: causal chains, definitions, trade-offs, coexisting concerns, priorities, information sources, and actor-specific qualifications.

Each coded response is represented as an ordered sequence of tokens. Tokens are separated by spaces, except when parentheses or square brackets are attached to a topic token.

## Token Types

| Token type | Example | Interpretation |
|---|---|---|
| Substantive topic | `carbon_tax`, `fuel_price_increase` | A conceptual node in the participant's reasoning. |
| Causal or logical operator | `-->` | A positive link: `A --> B` means that A leads to B in the response. |
| Definition operator | `=` | `A = B` means that the participant defines or frames A as B. |
| Distinct path separator | `;` | Separates two narrative components within the same response. |
| Additive operator | `+` | `A + B` means that A and B form a combined policy, package, or bundle. |
| Coexistence operator | `&` | `A & B` means that A and B coexist without additive meaning. |
| Priority operators | `<`, `>` | `A < B` means B prevails over A; `A > B` means A prevails over B. |
| Source marker | `|` | `A --> B | newspaper` records an information source. |
| Aggregated topic | `green_transport_development (electric_vehicle_infrastructure, soft_mobility)` | A broad topic with more specific subtopics. |
| Scope-qualified topic | `fuel_price_increase[others]` | A topic qualified by the actor, group, or standpoint concerned. |

## Normalization Rules

Substantive topics are lowercased. Multi-word concepts use underscores:

```text
future_environmental_benefits
purchasing_power_loss
economic_environmental_trade_off
```

Internal spaces are removed during normalization. The preferred written form is therefore compact and explicit.

## Directional Topic Labels

The arrow `-->` always encodes a positive causal or logical relation. The direction of variation must be placed in the topic label itself. Coders should therefore prefer directional labels:

```text
fuel_price_increase
fuel_price_decrease
inflation
deflation
purchasing_power_loss
purchasing_power_gain
carbon_emission_reduction
carbon_emission_increase
```

Neutral labels such as `fuel_price`, `price_level`, or `carbon_emissions` should be avoided when the direction of change matters.

For example:

```text
carbon_tax --> fuel_price_increase --> unacceptability
carbon_tax --> fuel_price_decrease --> acceptability
```

Both sequences use a positive arrow, but they encode substantively different mechanisms because the direction is carried by the node labels.

## Aggregated Topics

Parentheses attach subtopics to a broader concept:

```text
green_transport_development (electric_vehicle_infrastructure, soft_mobility)
```

This indicates that electric vehicle infrastructure and soft mobility are treated as components of green transport development in the participant's reasoning.

Aggregated topics can appear inside longer sequences:

```text
alternative_policy = carbon_tax + green_transport_development (electric_vehicle_infrastructure, soft_mobility) --> acceptability
```

## Scope Qualifiers

Square brackets indicate the actor, group, social position, or point of view to which a node applies:

```text
fuel_price_increase[others]
no_current_car_dependency[self]
potential_direct_impact[future_self]
```

Composite scopes are allowed:

```text
unreadiness[modest_household, company (agricultural_sector, sme)]
```

The outer square brackets attach the whole scope to the topic. Parentheses inside the scope describe subgroups.

## Phase-Specific Coding Rules

### Top-of-Mind Phase

There is no required ending node. The coding should represent spontaneous associations, definitions, narrative paths, or information sources. When possible, sequences begin with:

```text
carbon_tax = ...
```

### Acceptability Phase

When analytically appropriate, the sequence should end with:

```text
acceptability
unacceptability
ambivalent_acceptability
```

Alternative or complementary policies can be introduced with:

```text
alternative_policy = ...
```

### Climate Anxiety Phase

The ending node should usually be the stated emotion or affective state. Mechanisms leading to that emotion appear before the emotional node.

### Final Phase

The sequence should synthesize the participant's final position while preserving the mechanism that explains it. When possible, it should end with `acceptability`, `unacceptability`, or `ambivalent_acceptability`.

## Cumulative Refinement Across Questions

Question-response pairs are not always treated as independent observations. When a question follows up on a previous answer, coders may reuse the previous relevant sequence as a backbone and refine it with new mechanisms, scope qualifiers, subtopics, or ending nodes.

This rule is applied only when the current response genuinely elaborates, qualifies, corrects, or deepens a previous line of reasoning. If the participant changes topic, rejects the previous framing, or adds no substantive information, the coding should reflect that shift. The code `none` is appropriate for explicitly non-substantive continuations.

## Validation Philosophy

The Streamlit apps warn about likely syntax issues, such as repeated operators, unbalanced brackets, or standalone scope punctuation. These warnings do not block saving because the final coding remains an interpretive qualitative act. They are designed to support consistency, not to replace coder judgment.
