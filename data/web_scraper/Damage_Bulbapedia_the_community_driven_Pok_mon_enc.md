---
title: "Damage - Bulbapedia, the community-driven Pokémon encyclopedia"
url: "https://bulbapedia.bulbagarden.net/wiki/Damage"
timestamp: "2026-03-30T22:57:30.756694+02:00"
---

# Damage

From Bulbapedia, the community-driven Pokémon encyclopedia.

Ash's Pokémon injured after a battle

**Damage** (Japanese: **ダメージ** *damage*) is a loss of a Pokémon's HP that happens as the result of a physical or special attack used against it by another Pokémon.

## Damage calculation

|  | **This section is incomplete.**  
Please feel free to edit this section to add missing information and complete it.  
Reason: Anything that may have potentially been missed or inaccurate |
| --- | --- |

Except for moves that deal direct damage, the damage dealt when a Pokémon uses a damaging move depends on its level, its effective Attack or Special Attack stat, the opponent's effective Defense or Special Defense stat, and the move's effective power. In addition, various factors of damage modification may also affect the damage dealt.

More precisely, damage is calculated in each Generation as:

### Generation I

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>D</mi><mi>a</mi><mi>m</mi><mi>a</mi><mi>g</mi><mi>e</mi><mo stretchy="false">=</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>2</mn><mo stretchy="false">×</mo><mi>L</mi><mi>e</mi><mi>v</mi><mi>e</mi><mi>l</mi><mo stretchy="false">×</mo><mi>C</mi><mi>r</mi><mi>i</mi><mi>t</mi><mi>i</mi><mi>c</mi><mi>a</mi><mi>l</mi></mrow></mrow><mrow data-mjx-texclass="ORD"><mn>5</mn></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>P</mi><mi>o</mi><mi>w</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>A</mi><mo lspace="0" rspace="0">/</mo><mi>D</mi></mrow></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>5</mn><mn>0</mn></mrow></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>S</mi><mi>T</mi><mi>A</mi><mi>B</mi><mo stretchy="false">×</mo><mi>T</mi><mi>y</mi><mi>p</mi><mi>e</mi><mn>1</mn><mo stretchy="false">×</mo><mi>T</mi><mi>y</mi><mi>p</mi><mi>e</mi><mn>2</mn><mo stretchy="false">×</mo><mi>r</mi><mi>a</mi><mi>n</mi><mi>d</mi><mi>o</mi><mi>m</mi></mstyle></mrow></math> --> Damage=((2×Level×Critical5+2)×Power×A/D50+2)×STAB×Type1×Type2×random

where:

- *Level* is the level of the attacking Pokémon.
- *Critical* is 2 for a critical hit, and 1 otherwise.
- *A* is the effective Attack stat of the attacking Pokémon if the used move is a physical move, or the effective Special stat of the attacking Pokémon if the used move is a special move (for a critical hit, all modifiers are ignored, and the unmodified Attack or Special is used instead). If either this or *D* are greater than 255, both are divided by 4 and rounded down.
- *D* is the effective Defense stat of the target if the used move is a physical move, or the effective Special stat of the target if the used move is an other special move (for a critical hit, all modifiers are ignored, and the unmodified Defense or Special is used instead). If the move is physical and the target has Reflect up, or if the move is special and the target has Light Screen up, this value is doubled (unless it is a critical hit). If the move is Explosion or Selfdestruct, this value is halved (rounded down, with a minimum of 1). If either this or *A* are greater than 255, both are divided by 4 and rounded down. Unlike future Generations, if this is 0, the division is not made equal to 0; rather, the game will try to divide by 0 and softlock, hanging indefinitely until it is turned off.
- *Power* is the power of the used move.
- *STAB* is the same-type attack bonus. This is equal to 1.5 if the move's type matches any of the user's types, and 1 if otherwise. Internally, it is recognized as an addition of the damage calculated thus far divided by 2, rounded down, then added to the damage calculated thus far.
- *Type1* is the type effectiveness of the used move against the target's type that comes first in the type matchup table, or only type if it only has one type. This can be 0.5 (not very effective), 1 (normally effective), 2 (super effective).
- *Type2* is the type effectiveness of the used move against the target's type that comes second in the type matchup table. This can be 0.5 (not very effective), 1 (normally effective), 2 (super effective). If the target only has one type, *Type2* is 1. If this would result in 0 damage, the calculation ends here and the move is stated to have missed, even if it would've hit.
- *random* is realized as a multiplication by a random uniformly distributed integer between 217 and 255 (inclusive), followed by an integer division by 255. If the calculated damage thus far is 1, *random* is always 1.

### Generation II

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>D</mi><mi>a</mi><mi>m</mi><mi>a</mi><mi>g</mi><mi>e</mi><mo stretchy="false">=</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>2</mn><mo stretchy="false">×</mo><mi>L</mi><mi>e</mi><mi>v</mi><mi>e</mi><mi>l</mi></mrow></mrow><mrow data-mjx-texclass="ORD"><mn>5</mn></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>P</mi><mi>o</mi><mi>w</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>A</mi><mo lspace="0" rspace="0">/</mo><mi>D</mi></mrow></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>5</mn><mn>0</mn></mrow></mrow></mfrac></mrow><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>I</mi><mi>t</mi><mi>e</mi><mi>m</mi><mo stretchy="false">×</mo><mi>C</mi><mi>r</mi><mi>i</mi><mi>t</mi><mi>i</mi><mi>c</mi><mi>a</mi><mi>l</mi><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>T</mi><mi>K</mi><mo stretchy="false">×</mo><mi>W</mi><mi>e</mi><mi>a</mi><mi>t</mi><mi>h</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>B</mi><mi>a</mi><mi>d</mi><mi>g</mi><mi>e</mi><mo stretchy="false">×</mo><mi>S</mi><mi>T</mi><mi>A</mi><mi>B</mi><mo stretchy="false">×</mo><mi>T</mi><mi>y</mi><mi>p</mi><mi>e</mi><mo stretchy="false">×</mo><mi>M</mi><mi>o</mi><mi>v</mi><mi>e</mi><mi>M</mi><mi>o</mi><mi>d</mi><mo stretchy="false">×</mo><mi>r</mi><mi>a</mi><mi>n</mi><mi>d</mi><mi>o</mi><mi>m</mi><mo stretchy="false">×</mo><mi>D</mi><mi>o</mi><mi>u</mi><mi>b</mi><mi>l</mi><mi>e</mi><mi>D</mi><mi>m</mi><mi>g</mi></mstyle></mrow></math> --> Damage=(((2×Level5+2)×Power×A/D50)×Item×Critical+2)×TK×Weather×Badge×STAB×Type×MoveMod×random×DoubleDmg

where:

- *Level* is the level of the attacking Pokémon. If the used move is Beat Up, *L* is instead the level of the Pokémon performing the strike.
- *A* is the effective Attack stat of the attacking Pokémon if the used move is a physical move, or the effective Special Attack stat of the attacking Pokémon if the used move is a special move (for a critical hit, if the target's Defense or Special Defense stat stage is greater than or equal to the attacker's Attack or Special Attack stat stage, all modifiers are ignored, and the unmodified Attack or Special is used instead). If the used move is Beat Up, *A* is instead the base Attack of the Pokémon performing the strike.
- *D* is the effective Defense stat of the target if the used move is a physical move, or the effective Special stat of the target if the used move is a special move (for a critical hit, all modifiers are ignored, and the unmodified Defense or Special is used instead). If the move is physical and the target has Reflect up, or if the move is special and the target has Light Screen up, this value is doubled (unless it is a critical hit). If the move is Explosion or Selfdestruct, this value is halved (rounded down, with a minimum of 1). If the used move is Beat Up, *D* is instead the base Defense of the target.
- *Power* is the power of the used move.
- *Item* is 1.1 if the attacker is holding an type-enhancing held item corresponding to the attack type (for instance, the Magnet for an Electric-type move). Otherwise, this value is simply 1.
- *Critical* is 2 for a critical hit, and 1 otherwise. It is always is 1 if the used move is Flail, Reversal, or Future Sight.
- *TK* is 1, 2, or 3 for each successive hit of Triple Kick, or always 1 if the used move is not Triple Kick.
- *Weather* is 1.5 if a Water-type move is being used during rain or a Fire-type move during harsh sunlight, and 0.5 if a Water-type move is used during harsh sunlight or SolarBeam or any Fire-type move during rain, and 1 otherwise.
- *Badge* is 1.125 if the attacking Pokémon is controlled by the player and if the player has obtained the Badge corresponding to the used move's type, and 1 otherwise. This bonus is not applied in link battles or the Battle Tower.
- *STAB* is the same-type attack bonus. This is equal to 1.5 if the move's type matches any of the user's types, and 1 if otherwise.
- *Type* is the type effectiveness. This can be 0.25, 0.5 (not very effective), 1 (normally effective), 2, or 4 (super effective), depending on both the move's and target's types. If the used move is Struggle, Future Sight, or Beat Up, *Type* is always 1.
- *MoveMod* can be (and if the used move is not any of these, *MoveMod* is 1):
  * If Rollout is used, <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><msup><mn>2</mn><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mi>n</mi><mo stretchy="false">+</mo><mi>d</mi><mo data-mjx-texclass="CLOSE">)</mo></mrow></mrow></msup></mstyle></mrow></math> --> 2(n+d), where *n* is the amount of successful and consecutive hits of the move, up to 4 (for the fifth hit), and *d* is 1 if Defense Curl was used beforehand and 0 otherwise.
  * If Fury Cutter is used, <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><msup><mn>2</mn><mrow data-mjx-texclass="ORD"><mi>n</mi></mrow></msup></mstyle></mrow></math> --> 2n, where *n* is the number of successful and consecutive uses of the move, up to 4.
  * If Rage is used, an integer value corresponding to the Rage counter, i.e. the number of times the user of Rage has been damaged by an attack while using Rage.
- *random* is realized as a multiplication by a random uniformly distributed integer between 217 and 255 (inclusive), followed by an integer division by 255. *random* is always 1 if Flail or Reversal is used.
- *DoubleDmg* is 2 if the used move is Pursuit and the target is attempting to switch out, Stomp and the target has previously used Minimize, Gust or Twister and the target is in the semi-invulnerable turn of Fly, or Earthquake or Magnitude and the target is in the semi-invulnerable turn of Dig, and 1 otherwise.

### Generation III

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>D</mi><mi>a</mi><mi>m</mi><mi>a</mi><mi>g</mi><mi>e</mi><mo stretchy="false">=</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>2</mn><mo stretchy="false">×</mo><mi>L</mi><mi>e</mi><mi>v</mi><mi>e</mi><mi>l</mi></mrow></mrow><mrow data-mjx-texclass="ORD"><mn>5</mn></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>P</mi><mi>o</mi><mi>w</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>A</mi><mo lspace="0" rspace="0">/</mo><mi>D</mi></mrow></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>5</mn><mn>0</mn></mrow></mrow></mfrac></mrow><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>B</mi><mi>u</mi><mi>r</mi><mi>n</mi><mo stretchy="false">×</mo><mi>S</mi><mi>c</mi><mi>r</mi><mi>e</mi><mi>e</mi><mi>n</mi><mo stretchy="false">×</mo><mi>T</mi><mi>a</mi><mi>r</mi><mi>g</mi><mi>e</mi><mi>t</mi><mi>s</mi><mo stretchy="false">×</mo><mi>W</mi><mi>e</mi><mi>a</mi><mi>t</mi><mi>h</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>F</mi><mi>F</mi><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>S</mi><mi>t</mi><mi>o</mi><mi>c</mi><mi>k</mi><mi>p</mi><mi>i</mi><mi>l</mi><mi>e</mi><mo stretchy="false">×</mo><mi>C</mi><mi>r</mi><mi>i</mi><mi>t</mi><mi>i</mi><mi>c</mi><mi>a</mi><mi>l</mi><mo stretchy="false">×</mo><mi>D</mi><mi>o</mi><mi>u</mi><mi>b</mi><mi>l</mi><mi>e</mi><mi>D</mi><mi>m</mi><mi>g</mi><mo stretchy="false">×</mo><mi>C</mi><mi>h</mi><mi>a</mi><mi>r</mi><mi>g</mi><mi>e</mi><mo stretchy="false">×</mo><mi>H</mi><mi>H</mi><mo stretchy="false">×</mo><mi>S</mi><mi>T</mi><mi>A</mi><mi>B</mi><mo stretchy="false">×</mo><mi>T</mi><mi>y</mi><mi>p</mi><mi>e</mi><mn>1</mn><mo stretchy="false">×</mo><mi>T</mi><mi>y</mi><mi>p</mi><mi>e</mi><mn>2</mn><mo stretchy="false">×</mo><mi>r</mi><mi>a</mi><mi>n</mi><mi>d</mi><mi>o</mi><mi>m</mi></mstyle></mrow></math> --> Damage=(((2×Level5+2)×Power×A/D50)×Burn×Screen×Targets×Weather×FF+2)×Stockpile×Critical×DoubleDmg×Charge×HH×STAB×Type1×Type2×random

where:

- *Level* is the level of the attacking Pokémon. If the used move is Beat Up, *L* is instead the level of the Pokémon performing the strike.
- *A* is the effective Attack stat of the attacking Pokémon if the used move is a physical move, or the effective Special Attack stat of the attacking Pokémon if the used move is a special move (for a critical hit, negative Attack or Special Attack stat stages are ignored). If the used move is Beat Up, *A* is instead the base Attack of the Pokémon performing the strike.
- *D* is the effective Defense stat of the target if the used move is a physical move, or the effective Special Defense stat of the target if the used move is a special move (for a critical hit, positive Defense or Special Defense stat stages are ignored). If the used move is Beat Up, *D* is instead the base Defense of the target.
- *Power* is the effective power of the used move.
- *Burn* is 0.5 if the attacker is burned, its Ability is not Guts, and the used move is a physical move, and 1 otherwise.
- *Screen* is 0.5 if the used move is physical and Reflect is present on the target's side of the field, or special and Light Screen is present. For a Double Battle, *Screen* is instead 2/3, and 1 otherwise or if the used move lands a critical hit. However, if, in a Double Battle, when the move is executed, the only Pokémon on the target's side is the target, *Screen* remains as 0.5.
- *Targets* is 0.5 in Double Battles if the move targets both foes (unless it targets all other Pokémon, like Earthquake, and only if there is more than one such target when the move is executed, regardless of whether the move actually hits or can hit all the targets), and 1 otherwise.
- If the base damage after applying *Targets* is 0 and the move is physical the base damage is increased by one.
- *Weather* is 1.5 if a Water-type move is being used during rain or a Fire-type move during harsh sunlight, and 0.5 if a Water-type move is used during harsh sunlight, any Fire-type move during rain, or SolarBeam during any non-clear weather besides harsh sunlight, and 1 otherwise or if any Pokémon on the field have the Ability Cloud Nine or Air Lock.
- *FF* is 1.5 if the used move is Fire-type, and the attacker's Ability is Flash Fire that has been activated by a Fire-type move, and 1 otherwise.
- *Stockpile* is 1, 2, or 3 if the used move is Spit Up, depending on how many Stockpiles have been used, or always 1 if the used move is not Spit Up.
- *Critical* is 2 for a critical hit, and 1 otherwise. It is always 1 if Future Sight, Doom Desire, or Spit Up is used, if the target's Ability is Battle Armor or Shell Armor, or if the battle is the first one against Poochyena**RS**/Zigzagoon**E** or the capture tutorial where Wally catches a Ralts.
- *DoubleDmg* is 2 if the used move is (and 1 if the used move is not any of these moves):
  * Gust or Twister and the target is in the semi-invulnerable turn of Fly or Bounce.
  * Stomp, Needle Arm, Astonish, or Extrasensory and the target has previously used Minimize.
  * Surf or Whirlpool and the target is in the semi-invulnerable turn of Dive.
  * Earthquake or Magnitude and the target is in the semi-invulnerable turn of Dig.
  * Pursuit and the target is attempting to switch out.
  * Facade and the user is poisoned, burned, or paralyzed.
  * SmellingSalt and the target is paralyzed.
  * Revenge and the attacker has been damaged by the target this turn.
  * Weather Ball, there is non-clear weather, and no Pokémon on the field have the Ability Cloud Nine or Air Lock.
- *Charge* is 2 if the move is Electric-type and Charge takes effect, and 1 otherwise.
- *HH* is 1.5 if the attacker's ally in a Double Battle has used Helping Hand on it, and 1 otherwise.
- *STAB* is the same-type attack bonus. This is equal to 1.5 if the move's type matches any of the user's types and 1 if otherwise.
- *Type1* is the type effectiveness of the used move against the target's first type (or only type, if it only has a single type). This can be 0.5 (not very effective), 1 (normally effective), or 2 (super effective). If the used move is Struggle, Future Sight, Beat Up, or Doom Desire, both *Type1* and *Type2* are always 1.
- *Type2* is the type effectiveness of the used move against the target's second type. This can be 0.5 (not very effective), 1 (normally effective), or 2 (super effective). If the target only has a single type, *Type2* is 1.
- *random* is realized as a multiplication by a random uniformly distributed integer between 85 and 100 (inclusive), followed by an integer division by 100. *random* is always 1 if Spit Up is used.

### Generation IV

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>D</mi><mi>a</mi><mi>m</mi><mi>a</mi><mi>g</mi><mi>e</mi><mo stretchy="false">=</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>2</mn><mo stretchy="false">×</mo><mi>L</mi><mi>e</mi><mi>v</mi><mi>e</mi><mi>l</mi></mrow></mrow><mrow data-mjx-texclass="ORD"><mn>5</mn></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>P</mi><mi>o</mi><mi>w</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>A</mi><mo lspace="0" rspace="0">/</mo><mi>D</mi></mrow></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>5</mn><mn>0</mn></mrow></mrow></mfrac></mrow><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>B</mi><mi>u</mi><mi>r</mi><mi>n</mi><mo stretchy="false">×</mo><mi>S</mi><mi>c</mi><mi>r</mi><mi>e</mi><mi>e</mi><mi>n</mi><mo stretchy="false">×</mo><mi>T</mi><mi>a</mi><mi>r</mi><mi>g</mi><mi>e</mi><mi>t</mi><mi>s</mi><mo stretchy="false">×</mo><mi>W</mi><mi>e</mi><mi>a</mi><mi>t</mi><mi>h</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>F</mi><mi>F</mi><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>C</mi><mi>r</mi><mi>i</mi><mi>t</mi><mi>i</mi><mi>c</mi><mi>a</mi><mi>l</mi><mo stretchy="false">×</mo><mi>I</mi><mi>t</mi><mi>e</mi><mi>m</mi><mo stretchy="false">×</mo><mi>F</mi><mi>i</mi><mi>r</mi><mi>s</mi><mi>t</mi><mo stretchy="false">×</mo><mi>r</mi><mi>a</mi><mi>n</mi><mi>d</mi><mi>o</mi><mi>m</mi><mo stretchy="false">×</mo><mi>S</mi><mi>T</mi><mi>A</mi><mi>B</mi><mo stretchy="false">×</mo><mi>T</mi><mi>y</mi><mi>p</mi><mi>e</mi><mn>1</mn><mo stretchy="false">×</mo><mi>T</mi><mi>y</mi><mi>p</mi><mi>e</mi><mn>2</mn><mo stretchy="false">×</mo><mi>S</mi><mi>R</mi><mi>F</mi><mo stretchy="false">×</mo><mi>E</mi><mi>B</mi><mo stretchy="false">×</mo><mi>T</mi><mi>L</mi><mo stretchy="false">×</mo><mi>B</mi><mi>e</mi><mi>r</mi><mi>r</mi><mi>y</mi></mstyle></mrow></math> --> Damage=(((2×Level5+2)×Power×A/D50)×Burn×Screen×Targets×Weather×FF+2)×Critical×Item×First×random×STAB×Type1×Type2×SRF×EB×TL×Berry

where:

- *Level* is the level of the attacking Pokémon. If the used move is Beat Up, *L* is instead the level of the Pokémon performing the strike.
- *A* is the effective Attack stat of the attacking Pokémon if the used move is a physical move, or the effective Special Attack stat of the attacking Pokémon if the used move is a special move (for a critical hit, negative Attack or Special Attack stat stages are ignored). If the used move is Beat Up, *A* is instead the base Attack of the Pokémon performing the strike.
- *D* is the effective Defense stat of the target if the used move is a physical move, or the effective Special Defense stat of the target if the used move is a special move (for a critical hit, positive Defense or Special Defense stat stages are ignored). If the used move is Beat Up, *D* is instead the base Defense of the target.
- *Power* is the effective power of the used move.
- *Burn* is 0.5 if the attacker is burned, its Ability is not Guts, and the used move is a physical move, and 1 otherwise.
- *Screen* is 0.5 if the used move is physical and Reflect is present on the target's side of the field, or special and Light Screen is present. For a Double Battle, *Screen* is instead 2/3; however, if in a Double Battle when the move is executed, the only Pokémon on the target's side of the field is the target (for moves with only one target), or there is only one target when the move is executed (for moves with more than one target), *Screen* remains as 0.5. *Screen* is 1 otherwise or if the used move lands a critical hit.
- *Targets* is 0.75 in Double Battles if the used move has more than one target (provided there is more than one such target when the move is executed, regardless of whether the move actually hits or can hit all the targets), and 1 otherwise.
- *Weather* is 1.5 if a Water-type move is being used during rain or a Fire-type move during harsh sunlight, and 0.5 if a Water-type move is used during harsh sunlight or a Fire-type move during rain, or SolarBeam during any non-clear weather besides harsh sunlight, and 1 otherwise or if any Pokémon on the field have the Ability Cloud Nine or Air Lock.
- *FF* is 1.5 if the used move is Fire-type, and the attacker's Ability is Flash Fire that has been activated by a Fire-type move, and 1 otherwise.
- *Critical* is 2 for a critical hit, 3 if the move lands a critical hit and the attacker's Ability is Sniper, and 1 otherwise. It is always 1 if Future Sight or Doom Desire is used, the target's Ability is Battle Armor or Shell Armor, the target is under the effect of Lucky Chant, or if the battle is the first one against Starly**DP**.
- *Item* is 1.3 if the attacker is holding a Life Orb, <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mn>1</mn><mo stretchy="false">+</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mi>n</mi></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>1</mn><mn>0</mn></mrow></mrow></mfrac></mrow></mstyle></mrow></math> --> 1+n10 if the attacker is holding a Metronome, where *n* is the amount of times the same move has been successfully and consecutively used, up to 10, and 1 otherwise.
- *First* is 1.5 if the used move was stolen with Me First.
- *random* is realized a random integer from 85 to 100, inclusive, divided by 100. *random* is always 1 if Spit Up is used.
- *STAB* is the same-type attack bonus. This is equal to 1.5 if the move's type matches any of the user's types, 2 if the user of the move additionally has Adaptability, and 1 if otherwise.
- *Type1* is the type effectiveness of the used move against the target's first type (or only type, if it only has a single type). This can be 0.5 (not very effective), 1 (normally effective), or 2 (super effective). If the used move is Struggle, Future Sight, Beat Up, or Doom Desire, both *Type1* and *Type2* are always 1.
- *Type2* is the type effectiveness of the used move against the target's second type. This can be 0.5 (not very effective), 1 (normally effective), or 2 (super effective). If the target only has a single type, *Type2* is 1.
- *SRF* is 0.75 if the used move is super effective, the target's Ability is Solid Rock or Filter, and the attacker's Ability is not Mold Breaker, and 1 otherwise.
- *EB* is 1.2 if the used move is super effective and the attacker is holding an Expert Belt, and 1 otherwise.
- *TL* is 2 if the used move is not very effective and the attacker's Ability is Tinted Lens, and 1 otherwise.
- *Berry* is 0.5 if the used move is super effective and the target is holding the Berry that weakens it, or Normal-type and the target is holding a Chilan Berry, and 1 otherwise.

### Generation V onward

Unless otherwise specified, all divisions and multiplications past the initial base damage calculation are rounded to the nearest integer if the result is not an integer (rounding down at 0.5).

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>D</mi><mi>a</mi><mi>m</mi><mi>a</mi><mi>g</mi><mi>e</mi><mo stretchy="false">=</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>2</mn><mo stretchy="false">×</mo><mi>L</mi><mi>e</mi><mi>v</mi><mi>e</mi><mi>l</mi></mrow></mrow><mrow data-mjx-texclass="ORD"><mn>5</mn></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>P</mi><mi>o</mi><mi>w</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>A</mi><mo lspace="0" rspace="0">/</mo><mi>D</mi></mrow></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>5</mn><mn>0</mn></mrow></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>T</mi><mi>a</mi><mi>r</mi><mi>g</mi><mi>e</mi><mi>t</mi><mi>s</mi><mo stretchy="false">×</mo><mi>P</mi><mi>B</mi><mo stretchy="false">×</mo><mi>W</mi><mi>e</mi><mi>a</mi><mi>t</mi><mi>h</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>G</mi><mi>l</mi><mi>a</mi><mi>i</mi><mi>v</mi><mi>e</mi><mi>R</mi><mi>u</mi><mi>s</mi><mi>h</mi><mo stretchy="false">×</mo><mi>C</mi><mi>r</mi><mi>i</mi><mi>t</mi><mi>i</mi><mi>c</mi><mi>a</mi><mi>l</mi><mo stretchy="false">×</mo><mi>r</mi><mi>a</mi><mi>n</mi><mi>d</mi><mi>o</mi><mi>m</mi><mo stretchy="false">×</mo><mi>S</mi><mi>T</mi><mi>A</mi><mi>B</mi><mo stretchy="false">×</mo><mi>T</mi><mi>y</mi><mi>p</mi><mi>e</mi><mo stretchy="false">×</mo><mi>B</mi><mi>u</mi><mi>r</mi><mi>n</mi><mo stretchy="false">×</mo><mi>o</mi><mi>t</mi><mi>h</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>Z</mi><mi>M</mi><mi>o</mi><mi>v</mi><mi>e</mi><mo stretchy="false">×</mo><mi>T</mi><mi>e</mi><mi>r</mi><mi>a</mi><mi>S</mi><mi>h</mi><mi>i</mi><mi>e</mi><mi>l</mi><mi>d</mi></mstyle></mrow></math> --> Damage=((2×Level5+2)×Power×A/D50+2)×Targets×PB×Weather×GlaiveRush×Critical×random×STAB×Type×Burn×other×ZMove×TeraShield

where

- *Level* is the level of the attacking Pokémon.
- *A* is the effective Attack stat of the attacking Pokémon if the used move is a physical move, or the effective Special Attack stat of the attacking Pokémon if the used move is a special move (ignoring negative stat stages for a critical hit).
- *D* is the effective Defense stat of the target if the used move is a physical move or a special move that uses the target's Defense stat, or the effective Special Defense of the target if the used move is an other special move (ignoring positive stat stages for a critical hit).
- *Power* is the effective power of the used move.
- *Targets* is 0.75 (0.5 in Battle Royals) if the move has more than one target when the move is executed, and 1 otherwise.
- *PB* is 0.25 (0.5 in Generation VI) if the move is the second strike of Parental Bond, and 1 otherwise.
- *Weather* is 1.5 if a Water-type move is being used during rain or a Fire-type move or Hydro Steam during harsh sunlight, and 0.5 if a Water-type move (besides Hydro Steam) is used during harsh sunlight or a Fire-type move during rain, and 1 otherwise or if any Pokémon on the field have the Ability Cloud Nine or Air Lock.
- *GlaiveRush* is 2 if the target used the move Glaive Rush in the previous turn, or 1 otherwise.
- *Critical* is 1.5 (2 in Generation V) for a critical hit, and 1 otherwise. Decimals are rounded down to the nearest integer. It is always 1 if the target's Ability is Battle Armor or Shell Armor or if the target is under the effect of Lucky Chant.
  * Conversely, unless critical hits are prevented entirely by one of the above effects, *Critical* will always be 1.5 (or 2 in Generation V) if the used move is Storm Throw, Frost Breath, Zippy Zap, Surging Strikes, Wicked Blow, or Flower Trick, the target is poisoned and the attacker's Ability is Merciless, or if the user is under the effect of Laser Focus.
- *random* is a random factor. Namely, it is recognized as a multiplication from a random integer between 85 and 100, inclusive, then divided by 100.
  * If the battle is taking place as a Pokéstar Studios film, *random* is always 1.
- *STAB* is the same-type attack bonus. This is equal to 1.5 if the move's type matches any of the user's types, 2 if the user of the move additionally has Adaptability, and 1 otherwise or if the attacker and/or used move is typeless. If the used move is a combination Pledge move, *STAB* is always 1.5 (or 2 if the user's Ability is Adaptability). When Terastallized, *STAB* is (if not 1):
  * 1.5 if the move's type matches either the Pokemon's original type(s) or a different Tera Type from its original types, and the attacker's Ability is not Adaptability.
  * 2 if the move's type matches the same Tera Type as one of the Pokemon's original types and the attacker's Ability is not Adaptability, or the situation above, if the attacker's Ability is Adaptability.
    + However, if STAB only applies from the attacker's original type(s), not its Tera Type, *STAB* will always be 1.5, even if the attacker's Ability is Adaptability.
  * 2.25 if the move's type matches the same Tera Type as one of the Pokemon's original types and the attacker's Ability is Adaptability.
- *Type* is the type effectiveness. This can be 0.125, 0.25, 0.5 (not very effective); 1 (normally effective); 2, 4, or 8 (super effective), depending on both the move's and target's types. The 0.125 and 8 can potentially be obtained on a Pokémon under the effect of Forest's Curse or Trick-or-Treat. If the used move is Struggle or typeless Revelation Dance, or the target is typeless, *Type* is always 1. Decimals are rounded down to the nearest integer. Certain effects can modify this, namely:
  * If the target is an ungrounded Flying-type that is not being grounded by any other effect and is holding an Iron Ball or under the effect of Thousand Arrows, *Type* is equal to 1.
  * If the target is a grounded Flying-type (unless grounded by an Iron Ball or Thousand Arrows, as above), treat Ground's matchup against Flying as 1.
  * If the target is holding a Ring Target and the used move is of a type it would otherwise be immune to, treat that particular type matchup as 1.
  * If the attacker's Ability is Scrappy, treat Normal and Fighting's type matchups against Ghost as 1.
  * If the target is under the effect of Foresight, Odor Sleuth or Miracle Eye, and the target is of a type that would otherwise grant immunity to the used move, treat that particular type matchup as 1.
  * If the used move is Freeze-Dry, treat the move's type's matchup against Water as 2.
  * If the used move is Flying Press, consider both the move's type effectiveness and the Flying type's against the target, and multiply them together.
  * If strong winds are in effect and the used move would be super effective against Flying, treat the type matchup against Flying as 1 instead.
  * If the target is under the effect of Tar Shot and the used move is Fire-type, multiply *Type* by 2.
- *Burn* is 0.5 if the attacker is burned, its Ability is not Guts, and the used move is a physical move (other than Facade from Generation VI onward), and 1 otherwise.
- *other* is 1 in most cases, and a different multiplier when specific interactions of moves, Abilities, or items take effect, in this order (and if multiple moves, Abilities, or items take effect, they do so in the order of the out-of-battle Speed stats of the Pokémon with them):

| Effect | Value | Detail |
| --- | --- | --- |
| Behemoth Blade, Behemoth Bash, and Dynamax Cannon | 2 | If the target is Dynamaxed and the used move is one of these three |
| Moves interacting with Minimize | 2 | If the target has used Minimize and the used move is one listed here |
| Earthquake and Magnitude | 2 | If the target is in the semi-invulnerable turn of Dig and the used move is one of these two |
| Surf and Whirlpool | 2 | If the target is in the semi-invulnerable turn of Dive and the used move is one of these two |
| Reflect, Light Screen, and Aurora Veil | 0.5 * | If in effect on the target's side, the used move is physical (Reflect), special (Light Screen), or either (Aurora Veil), the move is not a critical hit, and the user's Ability is not Infiltrator. Does not stack, even if e.g. Light Screen and Aurora Veil are active at the same time. |
| Collision Course and Electro Drift | 5461/4096 (~1.3333) | If either of these are the used move and it is super effective |
| Multiscale and Shadow Shield | 0.5 | If the target has this Ability and is at full health |
| Fluffy | 0.5 | If the target has this Ability and the used move makes contact |
| Punk Rock | 0.5 | If the target has this Ability and the used move is sound-based |
| Ice Scales | 0.5 | If the target has this Ability and the used move is a special move |
| Friend Guard | 0.75 | If an ally of the target has this Ability |
| Filter, Prism Armor and Solid Rock | 0.75 | If the target has this Ability and the used move is super effective (*Type* > 1) |
| Neuroforce | 1.25 | If the user has this Ability and the used move is super effective (*Type* > 1) |
| Sniper | 1.5 | If the attacker has this Ability and the move lands a critical hit |
| Tinted Lens | 2 | If the attacker has this Ability and the used move is not very effective (*Type* < 1) |
| Fluffy | 2 | If the target has this Ability and the used move is Fire-type |
| Type-resist Berries | 0.5 * | If held by the target, the move is of the corresponding type, and is super effective (*Type* > 1); for the Chilan Berry, the used move must simply only be Normal-type |
| Expert Belt | 4915/4096 (~1.2) | If held by the attacker and the move is super effective (*Type* > 1) |
| Life Orb | 5324/4096 (~1.3) | If held by the attacker |
| Metronome | Varies | 1 + (819/4096 (~0.2) per successful consecutive use of the same move) if held by the attacker, but no more than 2 |

If multiple effects influence the *other* value, their values stack multiplicatively, in the order listed above. This is done by starting at 4096, multiplying it by each number above in the order listed above, and rounding to the nearest integer whenever the result is not an integer (rounding up at 0.5). When the final value is obtained, it is divided by 4096, and this becomes *other*. For example, if both Multiscale and a Chilan Berry take effect, *other* is <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>4</mn><mn>0</mn><mn>9</mn><mn>6</mn><mo stretchy="false">×</mo><mn>0</mn><mo stretchy="false">.</mo><mn>5</mn><mo stretchy="false">×</mo><mn>0</mn><mo stretchy="false">.</mo><mn>5</mn></mrow></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>4</mn><mn>0</mn><mn>9</mn><mn>6</mn></mrow></mrow></mfrac></mrow></mstyle></mrow></math> --> 4096×0.5×0.54096 = 0.25.

- *ZMove* is 0.25 if the move is a Z-Move or Max Move and the target would be protected from that move (e.g. by Protect), and 1 otherwise. (If this multiplier is applied, a message is displayed that the target "couldn't fully protect" itself.)
- *TeraShield* is applied in Tera Raid Battles when the Raid boss's shield is active. It is 0.2 if the player's Pokémon is not Terastallized, 0.35 if it is but the used move is not of its Tera Type, and 0.75 if it is and the used move is of its Tera Type. The result is subject to standard rounding (rounding up at 0.5).

In the first four generations, during the calculation, all operations are carried out on integers internally—this means that all division operations are truncated integer division (i.e. rounding down if the result is not an integer), and the results of multiplication operations are rounded down afterwards (truncating any fractional part). From Generation V onward, there are three different types of rounding; a flooring (the same as previous generations), rounding to the nearest integer while rounding down at 0.5, and rounding to the nearest integer while rounding up at 0.5.

If the calculation yields 0, the move will deal 1 HP damage instead (unless *Type* is equal to 0, in which case damage calculation is skipped entirely); however, in Generation V, a move may deal 0 damage when *other* is less than 1, because the routine to prevent 0 damage is erroneously performed before applying the *other* factor.

### Example

Imagine a level 75 Glaceon that does not suffer a burn and holds no item with an effective Attack stat of 123 uses Ice Fang (an Ice-type physical move with a power of 65) against a Garchomp with an effective Defense stat of 163 in Generation VI, and does not land a critical hit. Then, the move will receive STAB, because Glaceon's Ice type matches the move's: *STAB* = 1.5. Additionally, Garchomp is Dragon/Ground, and therefore has a double weakness to the move's Ice type: *Type* = 4. All other (non-random) modifiers will be 1. This effectively gives

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mrow data-mjx-texclass="ORD"><mtable columnspacing="0em 2em 0em 2em 0em 2em 0em 2em 0em 2em 0em" columnalign="right left right left right left right left right left right left" displaystyle="true" rowspacing="3pt"><mtr><mtd><mi>D</mi><mi>a</mi><mi>m</mi><mi>a</mi><mi>g</mi><mi>e</mi></mtd><mtd><mo stretchy="false">=</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>2</mn><mo stretchy="false">×</mo><mn>7</mn><mn>5</mn></mrow></mrow><mrow data-mjx-texclass="ORD"><mn>5</mn></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mn>6</mn><mn>5</mn><mo stretchy="false">×</mo><mn>1</mn><mn>2</mn><mn>3</mn><mo lspace="0" rspace="0">/</mo><mn>1</mn><mn>6</mn><mn>3</mn></mrow></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>5</mn><mn>0</mn></mrow></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mn>1</mn><mo stretchy="false">×</mo><mn>1</mn><mo stretchy="false">×</mo><mn>1</mn><mo stretchy="false">×</mo><mn>1</mn><mo stretchy="false">×</mo><mo stretchy="false">(</mo><mi>r</mi><mi>a</mi><mi>n</mi><mi>d</mi><mo stretchy="false">∈</mo><mo stretchy="false">[</mo><mn>0</mn><mo stretchy="false">.</mo><mn>8</mn><mn>5</mn><mo>,</mo><mn>1</mn><mo stretchy="false">.</mo><mn>0</mn><mn>0</mn><mo stretchy="false">]</mo><mo stretchy="false">)</mo><mo stretchy="false">×</mo><mn>1</mn><mo stretchy="false">.</mo><mn>5</mn><mo stretchy="false">×</mo><mn>4</mn><mo stretchy="false">×</mo><mn>1</mn><mo stretchy="false">×</mo><mn>1</mn></mtd></mtr><mtr><mtd /><mtd><mo stretchy="false">=</mo><mi>r</mi><mi>a</mi><mi>n</mi><mi>d</mi><mo stretchy="false">∈</mo><mo stretchy="false">[</mo><mn>1</mn><mn>6</mn><mn>8</mn><mo>,</mo><mn>1</mn><mn>9</mn><mn>6</mn><mo stretchy="false">]</mo></mtd></mtr></mtable></mrow></mstyle></mrow></math> --> Damage=((2×755+2)×65×123/16350+2)×1×1×1×1×(rand∈[0.85,1.00])×1.5×4×1×1=rand∈[168,196]

That means Ice Fang will do between 168 and 196 HP damage, depending on luck.

If the same Glaceon holds a Muscle Band and its Ice Fang lands a critical hit against Garchomp, Ice Fang's effective power will be boosted by the Muscle Band by (approximately) 10% to become 71, and it will also be *Critical* = 1.5:

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mrow data-mjx-texclass="ORD"><mtable columnspacing="0em 2em 0em 2em 0em 2em 0em 2em 0em 2em 0em" rowspacing="3pt" columnalign="right left right left right left right left right left right left" displaystyle="true"><mtr><mtd><mi>D</mi><mi>a</mi><mi>m</mi><mi>a</mi><mi>g</mi><mi>e</mi></mtd><mtd><mo stretchy="false">=</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>2</mn><mo stretchy="false">×</mo><mn>7</mn><mn>5</mn></mrow></mrow><mrow data-mjx-texclass="ORD"><mn>5</mn></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mn>7</mn><mn>1</mn><mo stretchy="false">×</mo><mn>1</mn><mn>2</mn><mn>3</mn><mo lspace="0" rspace="0">/</mo><mn>1</mn><mn>6</mn><mn>3</mn></mrow></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>5</mn><mn>0</mn></mrow></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mn>1</mn><mo stretchy="false">×</mo><mn>1</mn><mo stretchy="false">×</mo><mn>1</mn><mo stretchy="false">×</mo><mn>1</mn><mo stretchy="false">.</mo><mn>5</mn><mo stretchy="false">×</mo><mo stretchy="false">(</mo><mi>r</mi><mi>a</mi><mi>n</mi><mi>d</mi><mo stretchy="false">∈</mo><mo stretchy="false">[</mo><mn>0</mn><mo stretchy="false">.</mo><mn>8</mn><mn>5</mn><mo>,</mo><mn>1</mn><mo stretchy="false">.</mo><mn>0</mn><mn>0</mn><mo stretchy="false">]</mo><mo stretchy="false">)</mo><mo stretchy="false">×</mo><mn>1</mn><mo stretchy="false">.</mo><mn>5</mn><mo stretchy="false">×</mo><mn>4</mn><mo stretchy="false">×</mo><mn>1</mn><mo stretchy="false">×</mo><mn>1</mn></mtd></mtr><mtr><mtd /><mtd><mo stretchy="false">=</mo><mi>r</mi><mi>a</mi><mi>n</mi><mi>d</mi><mo stretchy="false">∈</mo><mo stretchy="false">[</mo><mn>2</mn><mn>6</mn><mn>8</mn><mo>,</mo><mn>3</mn><mn>2</mn><mn>4</mn><mo stretchy="false">]</mo></mtd></mtr></mtable></mrow></mstyle></mrow></math> --> Damage=((2×755+2)×71×123/16350+2)×1×1×1×1.5×(rand∈[0.85,1.00])×1.5×4×1×1=rand∈[268,324]

That means Ice Fang will now do between 268 and 324 HP damage, depending on luck.

### Pokémon Legends: Arceus

In Pokémon Legends: Arceus, a new damage calculation method

All multiplications and divisions are rounded down to the nearest integer unless specified.

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>D</mi><mi>a</mi><mi>m</mi><mi>a</mi><mi>g</mi><mi>e</mi><mo stretchy="false">=</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mn>1</mn><mn>0</mn><mn>0</mn><mo stretchy="false">+</mo><mi>A</mi><mo stretchy="false">+</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mn>1</mn><mn>5</mn><mo stretchy="false">×</mo><mi>L</mi><mi>e</mi><mi>v</mi><mi>e</mi><mi>l</mi><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>P</mi><mi>o</mi><mi>w</mi><mi>e</mi><mi>r</mi><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo lspace="0" rspace="0">/</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mi>D</mi><mo stretchy="false">+</mo><mn>5</mn><mn>0</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow></mrow></mrow><mrow data-mjx-texclass="ORD"><mn>5</mn></mrow></mfrac></mrow><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mi>A</mi><mi>t</mi><mi>k</mi><mi>M</mi><mi>o</mi><mi>d</mi><mo stretchy="false">×</mo><mi>D</mi><mi>e</mi><mi>f</mi><mi>M</mi><mi>o</mi><mi>d</mi><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>r</mi><mi>a</mi><mi>n</mi><mi>d</mi><mi>o</mi><mi>m</mi><mo stretchy="false">×</mo><mi>T</mi><mi>y</mi><mi>p</mi><mi>e</mi><mo stretchy="false">×</mo><mi>O</mi><mi>t</mi><mi>h</mi><mi>e</mi><mi>r</mi><mi>M</mi><mi>o</mi><mi>d</mi><mi>s</mi></mstyle></mrow></math> --> Damage=(((100+A+(15×Level))×Power)/(D+50)5)×(AtkMod×DefMod)×random×Type×OtherMods

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>O</mi><mi>t</mi><mi>h</mi><mi>e</mi><mi>r</mi><mi>M</mi><mi>o</mi><mi>d</mi><mi>s</mi><mo stretchy="false">=</mo><mi>W</mi><mi>e</mi><mi>a</mi><mi>t</mi><mi>h</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>C</mi><mi>r</mi><mi>i</mi><mi>t</mi><mi>i</mi><mi>c</mi><mi>a</mi><mi>l</mi><mo stretchy="false">×</mo><mi>S</mi><mi>T</mi><mi>A</mi><mi>B</mi><mo stretchy="false">×</mo><mi>B</mi><mi>u</mi><mi>r</mi><mi>n</mi><mi>F</mi><mi>r</mi><mi>o</mi><mi>s</mi><mi>t</mi><mi>b</mi><mi>i</mi><mi>t</mi><mi>e</mi><mo stretchy="false">×</mo><mi>D</mi><mi>r</mi><mi>o</mi><mi>w</mi><mi>s</mi><mi>y</mi><mo stretchy="false">×</mo><mi>F</mi><mi>i</mi><mi>x</mi><mi>a</mi><mi>t</mi><mi>e</mi><mi>d</mi><mi>O</mi><mi>f</mi><mi>f</mi><mi>e</mi><mi>n</mi><mi>s</mi><mi>e</mi><mo stretchy="false">×</mo><mi>F</mi><mi>i</mi><mi>x</mi><mi>a</mi><mi>t</mi><mi>e</mi><mi>d</mi><mi>D</mi><mi>e</mi><mi>f</mi><mi>e</mi><mi>n</mi><mi>s</mi><mi>e</mi><mo stretchy="false">×</mo><mi>P</mi><mi>r</mi><mi>i</mi><mi>m</mi><mi>e</mi><mi>d</mi></mstyle></mrow></math> --> OtherMods=Weather×Critical×STAB×BurnFrostbite×Drowsy×FixatedOffense×FixatedDefense×Primed

where

- *Level* is the level of the attacking Pokémon.
- *A* is the effective Attack stat of the attacking Pokémon if the used move is a physical move, or the effective Special Attack stat of the attacking Pokémon if the used move is a special move.
  * If the attacker is under Slow Start, then the physical Attack stat will be halved at this step of the calculation.
  * If the attacker is filled with Wild Might or Terrible Might, both Attack stats will be multiplied by 1.5.
- *D* is the effective Defense stat of the target if the used move is a physical move, or the effective Special Defense of the target if the used move is an other special move.
  * If the target is filled with Wild Might or Terrible Might, both Defense stats will be multiplied by 1.5.
- *Power* is the power of the used move.
- *AtkMod* is 1.5 if the attacker's offensive stats are boosted, 1 if they are neutral, or 0.66 if they are lowered. If the attacker and target have the same "stage" of offensive and defensive stats, both this and *DefMod* are 1. This is applied by first multiplying *AtkMod* by *DefMod*, then multiplying the result by the calculated damage thus far and rounding down to the nearest integer.
- *DefMod* is 1.5 if the target's defensive stats are lowered, 1 if they are neutral, or 0.66 if they are boosted.
- *random* is realized as a multiplication by a random integer between 85 and 100 (inclusive), and divided by 100.
  * Splinter damage (from Ceaseless Edge, Pin Missile, Spikes, Stealth Rock and Stone Axe) is not subject to this factor.
- *Type* is the type effectiveness. This can be 0.4, 0.5 (not very effective); 1 (normally effective); 2, or 2.5 (super effective), depending on both the move's and target's types.
- *Weather* is 0.75 if a Fire-type move is used during rain, and 1 otherwise. The result is rounded to the nearest integer (rounding down at 0.5).
- *Critical* is 1.5 for a critical hit, and 1 otherwise.
- *STAB* is the same-type attack bonus. This is equal to 1.25 if the move's type matches any of the user's types, and 1 otherwise. The result is rounded to the nearest integer (rounding down at 0.5).
- *BurnFrostbite* is 0.5 if the attacker is burned and the used move is physical, or if the attacker is frostbitten and the used move is special, and 1 otherwise.
- *Drowsy* is 1.33 if the target is drowsy, and 1 otherwise.
- *FixatedOffense* is 1.5 if the attacker is fixated, and 1 otherwise.
- *FixatedDefense* is 1.33 if the target is fixated, and 1 otherwise.
- *Primed* is 1.5 if the attacker is primed, and 1 otherwise.

### Pokémon Legends: Z-A

In Pokémon Legends: Z-A, a damage calculation method similar to the one used from Generation V onwards is used, though it does feature its own share of differences from it:

All multiplications and divisions are rounded down to the nearest integer unless specified.

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>D</mi><mi>a</mi><mi>m</mi><mi>a</mi><mi>g</mi><mi>e</mi><mo stretchy="false">=</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mi>A</mi><mo stretchy="false">×</mo><mi>P</mi><mi>o</mi><mi>w</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>2</mn><mo stretchy="false">×</mo><mi>L</mi><mi>e</mi><mi>v</mi><mi>e</mi><mi>l</mi></mrow></mrow><mrow data-mjx-texclass="ORD"><mn>5</mn></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow></mrow></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>5</mn><mn>0</mn><mo stretchy="false">×</mo><mi>D</mi></mrow></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow><mo stretchy="false">×</mo><mi>W</mi><mi>e</mi><mi>a</mi><mi>t</mi><mi>h</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>C</mi><mi>r</mi><mi>i</mi><mi>t</mi><mi>i</mi><mi>c</mi><mi>a</mi><mi>l</mi><mo stretchy="false">×</mo><mi>r</mi><mi>a</mi><mi>n</mi><mi>d</mi><mi>o</mi><mi>m</mi><mo stretchy="false">×</mo><mi>S</mi><mi>T</mi><mi>A</mi><mi>B</mi><mo stretchy="false">×</mo><mi>T</mi><mi>y</mi><mi>p</mi><mi>e</mi><mo stretchy="false">×</mo><mi>B</mi><mi>u</mi><mi>r</mi><mi>n</mi><mo stretchy="false">×</mo><mi>o</mi><mi>t</mi><mi>h</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>P</mi><mi>r</mi><mi>o</mi><mi>t</mi><mi>e</mi><mi>c</mi><mi>t</mi><mo stretchy="false">×</mo><mn>0</mn><mo stretchy="false">.</mo><mn>7</mn></mstyle></mrow></math> --> Damage=(A×Power×(2×Level5+2)50×D+2)×Weather×Critical×random×STAB×Type×Burn×other×Protect×0.7

where

- *Level* is the level of the attacking Pokémon.
- *A* is the effective Attack stat of the attacking Pokémon if the used move is a physical move, or the effective Special Attack stat of the attacking Pokémon if the used move is a special move (ignoring stat drops for a critical hit).
  * It is multiplied by ×1.5 if the user's stat is boosted, or ×0.67 if the stat is dropped.
  * It is multiplied by ×2 if the user's Trainer has a red X Attack buff in the Z-A Battle Club.
  * It is multiplied by ×2 if the user is a wild alpha Pokémon
  * It can be multiplied by ×1.1, ×1.25, or ×1.5 if Levels 1, 2, or 3, respectively, of Attack Power or Sp. Atk Power is active.
- *D* is the effective Defense stat of the target if the used move is a physical move or a special move that uses the target's Defense stat, or the effective Special Defense of the target if the used move is an other special move (ignoring a stat boost for a critical hit).
  * It is multiplied by ×1.5 if the target's stat is boosted, or ×0.67 if the stat is dropped.
  * It is multiplied by ×2 if the target's Trainer has a blue X Defense buff in the Z-A Battle Club.
  * It is multiplied by ×2 if the target is a wild alpha Pokémon
  * It can be multiplied by ×1.1, ×1.25, or ×1.5 if Levels 1, 2, or 3, respectively, of Defense Power or Sp. Def Power is active.
  * It can be multiplied by ×<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mn>1</mn></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>0</mn><mo stretchy="false">.</mo><mn>9</mn></mrow></mrow></mfrac></mrow></mstyle></mrow></math> --> 10.9, ×<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mn>1</mn></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>0</mn><mo stretchy="false">.</mo><mn>8</mn></mrow></mrow></mfrac></mrow></mstyle></mrow></math> --> 10.8, or ×<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mn>1</mn></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>0</mn><mo stretchy="false">.</mo><mn>6</mn><mn>5</mn></mrow></mrow></mfrac></mrow></mstyle></mrow></math> --> 10.65 if Levels 1, 2, or 3, respectively, of Resistance Power is active and the type of the used move matches the type Resistance Power guards against.
- *Power* is the base power of the used move.
  * It can be multiplied by ×1.1, ×1.25, or ×1.5 if Levels 1, 2, or 3, respectively, of Move Power is active and the type of the used move matches the type Move Power boosts.
- *Weather* is 1.2 if a Water-type move is used during rain, 0.8 if a Fire-type move is used during rain, and 1 otherwise.
- *Critical* is 1.5 for a critical hit, and 1 otherwise. It will always be 1.5 if the attack was landed as a sneak attack on an opposing Trainer's Pokémon in a Z-A Royale or Hyperspace battle zone.
- *random* is a random factor. Namely, it is recognized as a multiplication from a random integer between 85 and 100, inclusive, then divided by 100.
- *STAB* is the same-type attack bonus. This is equal to 1.5 if the move's type matches any of the user's types, and 1 otherwise or if the attacker and/or used move is typeless.
- *Type* is the type effectiveness. The multiplier can be affected depending on if a Plus Move is used and if used against a Rogue Mega Evolution or equivalent boss battle. If a Plus Move is used against in a boss battle, the Plus Move multiplier is used.

| Effectiveness | Standard | | Boss | |
| --- | --- | --- | --- | --- |
|  | Base | Plus Move | Base | Plus Move |
| Super effective | 8× | 10.4× | 1.512× | 6.552× |
|  | 4× | 5.2× | 0.756× | 3.276× |
|  | 2× | 2.6× | 0.6× | 2.6× |
| Normally effective | 1× | 1.2× | 0.3× | 1.2× |
| Not very effective | 0.6× | 0.72× | 0.18× | 0.72× |
|  | 0.3× | 0.36× | 0.09× | 0.36× |
|  | 0.15× | 0.18× | 0.045× | 0.18× |

- Against a boss, 0.3× is applied to non-Plus Moves, and 0.63× is applied to super effective moves with a 4× or higher type multiplier.
- The 0.15 and 8 (as well as the 0.18 and 10.4) can potentially be obtained on a Pokémon under the effect of Forest's Curse or Trick-or-Treat.
- If the target is typeless, *Type* is always 1; in Legends: Z-A, this is only used against the Hyperrogue Ange Floette flowers, which are considered to be typeless.
- If the attacker is a boss, and the target would otherwise be immune to the attack, *Type* is 0.3.
- If the target is an ungrounded Flying-type that is not being grounded by any other effect and is under the effect of Thousand Arrows, *Type* is equal to 1.
- If the target is a grounded Flying-type (unless grounded by an Thousand Arrows, as above), treat Ground's matchup against Flying as 1.
- If the used move is Freeze-Dry, treat the move's type's matchup against Water as 2.
- If the used move is Flying Press, consider both the move's type effectiveness and the Flying type's against the target, and multiply them together.

- *Burn* is 0.5 if the attacker is burned and the used move is a physical move, and 1 otherwise.
- *other* is 1 in most cases, and a different multiplier when specific interactions of moves or items take effect, in this order:

| Effect | Value | Detail |
| --- | --- | --- |
| Reflect and Light Screen | 0.66 | If in effect on the target's side, the used move is physical (Reflect) or special (Light Screen), and the move is not a critical hit. |
| Type-resist Berries | 0.5 | If held by the target, the move is of the corresponding type, and is super effective (*Type* > 1); for the Chilan Berry, the used move must simply only be Normal-type |
| Expert Belt | 1.2 | If held by the attacker and the move is super effective (*Type* > 1) |
| Life Orb | 1.3 | If held by the attacker |

If multiple effects influence the *other* value, their values stack multiplicatively, in the order listed above. This is done by starting with 1, multiplying the multipliers together, multiplying the final multiplier by the result thus far, and rounding down the result to the nearest integer.

- *Protect* is 0.25 if the move is a Plus Move and the target would be protected from that move (e.g. by Protect), and 1 if no protection is used. (If this multiplier is applied, a message is displayed that the target "couldn't fully protect" itself.)

If the calculation yields 0, the move will deal 1 HP damage instead (unless *Type* is equal to 0, in which case damage calculation is skipped entirely).

If the move would deal over 65535 damage, it will instead be capped at 65535; notably, this is different from in Generation V to Pokémon Scarlet and Violet, where the damage instead would roll over to 0 at 65536.

### Pokémon GO

In Pokémon GO, damage is calculated differently due to different variables existing in the game.

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>D</mi><mi>a</mi><mi>m</mi><mi>a</mi><mi>g</mi><mi>e</mi><mo stretchy="false">=</mo><mi>M</mi><mi>u</mi><mi>s</mi><mi>h</mi><mi>r</mi><mi>o</mi><mi>o</mi><mi>m</mi><mo stretchy="false">×</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">⌊</mo><mn>0</mn><mo stretchy="false">.</mo><mn>5</mn><mo stretchy="false">×</mo><mi>P</mi><mi>o</mi><mi>w</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mi>A</mi><mi>t</mi><mi>t</mi><mi>a</mi><mi>c</mi><mi>k</mi></mrow></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mi>D</mi><mi>e</mi><mi>f</mi><mi>e</mi><mi>n</mi><mi>s</mi><mi>e</mi></mrow></mrow></mfrac></mrow><mo stretchy="false">×</mo><mi>M</mi><mi>o</mi><mi>d</mi><mi>i</mi><mi>f</mi><mi>i</mi><mi>e</mi><mi>r</mi><mo data-mjx-texclass="CLOSE">⌋</mo></mrow><mo stretchy="false">+</mo><mn>1</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow></mstyle></mrow></math> --> Damage=Mushroom×(⌊0.5×Power×AttackDefense×Modifier⌋+1)

where

- *Mushroom* is 2 if there is an active Max Mushroom and is 1 otherwise.
- *Power* is the power of the move used
- *Attack* is the Attack stat of the attacking Pokémon
- *Defense* is the Defense stat of the Pokémon being attacked
- For Shadow Pokémon:
  * <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mo stretchy="false">×</mo><mrow data-mjx-texclass="ORD"><mstyle displaystyle="false" scriptlevel="0"><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mn>6</mn></mrow><mrow data-mjx-texclass="ORD"><mn>5</mn></mrow></mfrac></mrow></mstyle></mrow></mstyle></mrow></math> --> ×65 is applied to *Attack*
  * <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mo stretchy="false">×</mo><mrow data-mjx-texclass="ORD"><mstyle displaystyle="false" scriptlevel="0"><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mn>5</mn></mrow><mrow data-mjx-texclass="ORD"><mn>6</mn></mrow></mfrac></mrow></mstyle></mrow></mstyle></mrow></math> --> ×56 is applied to *Defense*

and

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>M</mi><mi>o</mi><mi>d</mi><mi>i</mi><mi>f</mi><mi>i</mi><mi>e</mi><mi>r</mi><mo stretchy="false">=</mo><mi>T</mi><mi>y</mi><mi>p</mi><mi>e</mi><mo stretchy="false">×</mo><mi>S</mi><mi>T</mi><mi>A</mi><mi>B</mi><mo stretchy="false">×</mo><mi>W</mi><mi>e</mi><mi>a</mi><mi>t</mi><mi>h</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>F</mi><mi>r</mi><mi>i</mi><mi>e</mi><mi>n</mi><mi>d</mi><mi>s</mi><mi>h</mi><mi>i</mi><mi>p</mi><mo stretchy="false">×</mo><mi>D</mi><mi>o</mi><mi>d</mi><mi>g</mi><mi>e</mi><mi>d</mi><mo stretchy="false">×</mo><mi>M</mi><mi>e</mi><mi>g</mi><mi>a</mi><mo stretchy="false">×</mo><mi>T</mi><mi>r</mi><mi>a</mi><mi>i</mi><mi>n</mi><mi>e</mi><mi>r</mi><mo stretchy="false">×</mo><mi>C</mi><mi>h</mi><mi>a</mi><mi>r</mi><mi>g</mi><mi>e</mi><mo stretchy="false">×</mo><mi>P</mi><mi>a</mi><mi>r</mi><mi>t</mi><mi>y</mi><mo stretchy="false">×</mo><mi>S</mi><mi>u</mi><mi>p</mi><mi>p</mi><mi>o</mi><mi>r</mi><mi>t</mi><mo stretchy="false">×</mo><mi>S</mi><mi>p</mi><mi>r</mi><mi>e</mi><mi>a</mi><mi>d</mi><mo stretchy="false">×</mo><mi>B</mi><mi>e</mi><mi>h</mi><mi>e</mi><mi>m</mi><mi>o</mi><mi>t</mi><mi>h</mi><mi>B</mi><mi>l</mi><mi>a</mi><mi>d</mi><mi>e</mi><mo stretchy="false">×</mo><mi>B</mi><mi>e</mi><mi>h</mi><mi>e</mi><mi>m</mi><mi>o</mi><mi>t</mi><mi>h</mi><mi>B</mi><mi>a</mi><mi>s</mi><mi>h</mi><mo stretchy="false">×</mo><mi>S</mi><mi>h</mi><mi>i</mi><mi>e</mi><mi>l</mi><mi>d</mi></mstyle></mrow></math> --> Modifier=Type×STAB×Weather×Friendship×Dodged×Mega×Trainer×Charge×Party×Support×Spread×BehemothBlade×BehemothBash×Shield

where

- *Type* is the type effectiveness, which is calculated differently in GO, using multipliers of base 1.6 instead of 2.
- *STAB* is the same-type attack bonus. This is equal to 1.2 if the move's type matches any of the user's types, and 1 if otherwise.
- The following variables are applied in Gym, Raid Battles, and Max Battles only, and are 1 otherwise.
  * *Weather* is 1.2 if the move used has a weather-boosted type, and 1 otherwise.
  * *Friendship* is applied when battling with Friends and varies depending on the Friendship level.
    + 1.03 if Good Friends
    + 1.05 if Great Friends
    + 1.07 if Ultra Friends
    + 1.1 if Best Friends
    + 1.12 if Forever Friends
    + 1 otherwise
  * *Dodged* is 0.25 if the attack was successfully dodged, and 1 if otherwise.
    + Gym defenders and Raid Bosses will never dodge a player's attacks
  * *Mega* is greater than 1 when there is one or more Mega-Evolved Pokémon on the battlefield.
    + 1.1 if none of the Mega-Evolved Pokémon have the same type as the move
    + 1.3 if one or more Mega-Evolved Pokémon have the same type as the move
  * *Party* is 2 if the charge-move has been boosted by Party Play, and 1 otherwise.
  * *BehemothBash* is applied when the defender has the Behemoth Bash adventure effect and varies depending on the battlefield used
    + 0.9090909091 in Raid Battles
    + 0.9523809524 in Max Battles
  * *BehemothBlade* is applied when the attacker has the Behemoth Blade adventure effect and varies depending on the battlefield used
    + 1.1 in Raid Battles
    + 1.05 in Max Battles
- The following variables are applied in Trainer Battles only, and are 1 otherwise.
  * *Trainer* is 1.3 for all attacks used in a Trainer Battle.
  * *Charge* is applied only for Charged Attacks, and its value depends on the player's score during the minigame. The possible ranges are
    + <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>C</mi><mi>h</mi><mi>a</mi><mi>r</mi><mi>g</mi><mi>e</mi><mo stretchy="false">=</mo><mn>1</mn></mstyle></mrow></math> --> Charge=1 if *"Excellent!"*
    + <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>C</mi><mi>h</mi><mi>a</mi><mi>r</mi><mi>g</mi><mi>e</mi><mo stretchy="false">∈</mo><mo stretchy="false">[</mo><mn>0</mn><mo stretchy="false">.</mo><mn>7</mn><mn>5</mn><mo>,</mo><mn>1</mn><mo stretchy="false">)</mo></mstyle></mrow></math> --> Charge∈[0.75,1) if *"Great!"*
    + <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>C</mi><mi>h</mi><mi>a</mi><mi>r</mi><mi>g</mi><mi>e</mi><mo stretchy="false">∈</mo><mo stretchy="false">[</mo><mn>0</mn><mo stretchy="false">.</mo><mn>5</mn><mo>,</mo><mn>0</mn><mo stretchy="false">.</mo><mn>7</mn><mn>5</mn><mo stretchy="false">)</mo></mstyle></mrow></math> --> Charge∈[0.5,0.75) if *"Nice!"*
    + <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mi>C</mi><mi>h</mi><mi>a</mi><mi>r</mi><mi>g</mi><mi>e</mi><mo stretchy="false">∈</mo><mo stretchy="false">[</mo><mn>0</mn><mo stretchy="false">.</mo><mn>2</mn><mn>5</mn><mo>,</mo><mn>0</mn><mo stretchy="false">.</mo><mn>5</mn><mo stretchy="false">)</mo></mstyle></mrow></math> --> Charge∈[0.25,0.5) otherwise
  * *Shield* is 0 if an attack was protected by a Protect Shield, and is 1 otherwise.
- The following variable is applied in Max Battles only, and are 1 otherwise.
  * *Support* is applied when there are Pokémon placed at the Power Spot.
    + 1.1 if 1 Pokémon placed (1 support icon)
    + 1.15 if 2-3 Pokémon placed (2 support icons)
    + 1.188 if 4-14 Pokémon placed (3 support icons)
    + 1.2 if 15 or more Pokémon placed (4 support icons)
    + 1 otherwise
  * *Spread* is 2 if the Max Battle Boss uses a single-target attack and is 1 otherwise.

By the damage formula, moves that have a power of 0 such as Splash and Yawn and moves shielded by Protect Shields will always do 1 HP damage.

### Pokémon Masters EX

|  | **This section is incomplete.**  
Please feel free to edit this section to add missing information and complete it.  
Reason: The damage formula is broken down in full here, just needs to be condensed/formatted for our purposes |
| --- | --- |

## Trivia

- In Pokémon Ruby and Sapphire, if the player's Pokémon deals over 33037 HP damage, the Pokémon will faint, but the HP bar will not be drained; if it deals exactly 33037 HP, the HP bar will be drained automatically.
- In Generation V onward, the amount of damage that can be dealt in a single attack is capped at 65535. In addition, an overflow can occur during the calculation of very high damage amounts, causing the actual damage dealt to be much lower than expected.
- In Generations I through IV, due to integer truncation, the multiplier <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML" class="mwe-math-element"><mrow data-mjx-texclass="ORD"><mstyle displaystyle="true" scriptlevel="0"><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="INNER"><mo data-mjx-texclass="OPEN">(</mo><mrow data-mjx-texclass="ORD"><mfrac><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>2</mn><mo stretchy="false">×</mo><mi>L</mi><mi>e</mi><mi>v</mi><mi>e</mi><mi>l</mi></mrow></mrow><mrow data-mjx-texclass="ORD"><mn>5</mn></mrow></mfrac></mrow><mo stretchy="false">+</mo><mn>2</mn><mo data-mjx-texclass="CLOSE">)</mo></mrow></mrow><mrow data-mjx-texclass="ORD"><mrow data-mjx-texclass="ORD"><mn>5</mn><mn>0</mn></mrow></mrow></mfrac></mrow></mstyle></mrow></math> --> (2×Level5+2)50 in the damage calculation increased at levels ending in 0, 3, 5, or 8.
- In Pokémon Battle Revolution, the HP bar will change with a different animation depending on the move's type (recovery, recoil damage, and indirect damage use the Normal-type animation), as shown below.


| --- | --- | --- | --- |
| Normal | Fighting | Flying | Poison |

| Ground | Rock | Bug | Ghost |

| Steel | Fire | Water | Grass |

| Electric | Psychic | Ice | Dragon |

| Dark |  |

## In other languages

| Language | | Title |
| --- | --- | --- |
| Chinese | Cantonese | 傷害 *Sēunghoih* |
|  | Mandarin | 傷害 / 伤害 *Shānghài* |
| Czech | | Poškození |
| Danish | | Skade |
| Finnish | | Vahinko |
| French | Canada | Tort* |
|  | Europe | Dégâts |
| German | | Schaden |
| Hungarian | | Sebzés |
| Italian | | Danno |
| Korean | | 데미지 *Damage* |
| Norwegian | | Skade |
| Portuguese | Brazil | Dano |
|  | Portugal | Dano |
| Russian | | Урон |
| Spanish | | Daño |
| Swedish | | Skada |


## External links

- The Complete Damage Formula for Black & White (Smogon University)
- DaWoblefet’s Damage Dissertation- A Complete Guide to the Damage Formula

## References

|  | This game mechanic article is part of **Project Games**, a Bulbapedia project that aims to write comprehensive articles on the Pokémon games. |
| --- | --- |
