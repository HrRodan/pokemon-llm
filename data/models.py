from typing import Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Float, Boolean, Text


class Base(DeclarativeBase):
    pass


class Pokemon(Base):
    __tablename__ = "pokemons"

    id: Mapped[int] = mapped_column(primary_key=True, doc="Unique ID of the Pokemon")
    name: Mapped[str] = mapped_column(String, doc="Name of the Pokemon")
    hit_points: Mapped[int] = mapped_column(Integer, doc="Base HP stat")
    attack: Mapped[int] = mapped_column(Integer, doc="Base Attack stat")
    defense: Mapped[int] = mapped_column(Integer, doc="Base Defense stat")
    special_attack: Mapped[int] = mapped_column(Integer, doc="Base Special Attack stat")
    special_defense: Mapped[int] = mapped_column(
        Integer, doc="Base Special Defense stat"
    )
    speed: Mapped[int] = mapped_column(Integer, doc="Base Speed stat")
    type_1: Mapped[str] = mapped_column(
        String, doc="Primary type (e.g., 'fire', 'water')"
    )
    type_2: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, doc="Secondary type, if any"
    )
    ability_1: Mapped[str] = mapped_column(String, doc="First ability")
    ability_2: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, doc="Second ability, if any"
    )
    ability_hidden: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, doc="Hidden ability, if any"
    )
    height_m: Mapped[float] = mapped_column(Float, doc="Height in meters")
    weight_kg: Mapped[float] = mapped_column(Float, doc="Weight in kilograms")
    base_experience: Mapped[int] = mapped_column(Integer, doc="Base experience yield")
    base_happiness: Mapped[int] = mapped_column(
        Integer, doc="Base friendship/happiness value"
    )
    capture_rate: Mapped[int] = mapped_column(
        Integer, doc="Capture rate (higher is easier to catch)"
    )
    hatch_counter: Mapped[int] = mapped_column(
        Integer, doc="Steps to hatch egg (cycles)"
    )
    is_legendary: Mapped[bool] = mapped_column(Boolean, doc="True if Legendary")
    is_mythical: Mapped[bool] = mapped_column(Boolean, doc="True if Mythical")
    generation: Mapped[int] = mapped_column(Integer, doc="Generation introduced")

    # Text fields for comma-separated lists
    weak_against_1: Mapped[Optional[str]] = mapped_column(
        Text, doc="Comma-separated types weak against (derived from type 1?)"
    )
    weak_against_2: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Comma-separated types weak against (derived from type 2?)",
    )
    strong_against_1: Mapped[Optional[str]] = mapped_column(
        Text, doc="Comma-separated types strong against"
    )
    strong_against_2: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="Comma-separated types strong against"
    )

    # New fields
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        doc="True for exactly one form used as the default for each Pokémon",
    )
    species_name: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, doc="Name of the species (e.g. 'bulbasaur')"
    )
    evolution_chain: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Comma-separated list of pokemon in the evolution chain",
    )


class Move(Base):
    __tablename__ = "moves"

    id: Mapped[int] = mapped_column(
        primary_key=True, doc="Unique ID (optional, might be auto-increment)"
    )
    name: Mapped[str] = mapped_column(String, doc="Name of the move")
    type: Mapped[str] = mapped_column(String, doc="Elemental type of the move")
    power: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, doc="Base power"
    )
    accuracy: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, doc="Accuracy percentage"
    )
    power_points: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, doc="Base PP"
    )
    damage_class: Mapped[str] = mapped_column(
        String, doc="Category: physical, special, or status"
    )
    priority: Mapped[int] = mapped_column(Integer, doc="Move priority bracket")
    generation: Mapped[int] = mapped_column(Integer, doc="Generation introduced")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, doc="Name of the item")
    cost: Mapped[int] = mapped_column(Integer, doc="Cost to buy")
    category: Mapped[str] = mapped_column(String, doc="Item category")
    generation: Mapped[int] = mapped_column(Integer, doc="Generation introduced")
    effect: Mapped[str] = mapped_column(Text, doc="Description of effect")
