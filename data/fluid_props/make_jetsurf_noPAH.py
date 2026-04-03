import cantera as ct
from pathlib import Path

import os

# Get directory where THIS script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Change working directory to script location
os.chdir(script_dir)

print("Working directory set to:", os.getcwd())

INPUT = "jetsurf.yaml"
OUTPUT = "jetsurf_noPAH.yaml"

# Species to always remove first if present
SEED_REMOVE = {
    "C5H5",   # cyclopentadienyl
}

# Name patterns commonly used for aromatic / PAH chemistry.
# Adjust after printing your actual species list.
PATTERNS = [
    "A1", "A2", "A3", "A4",     # common aromatic shorthand in some mechanisms
    "BENZ", "PHEN", "NAPH",     # common textual roots
    "C5H5", "C6H5", "C6H6",     # cyclopentadienyl / phenyl / benzene
    "C7H7", "C7H8",             # benzyl / toluene family
    "INDENE", "INDENYL",
    "NAPH", "FLUORENE", "PYRENE"
]

def species_temp_limits(species_list):
    out = []
    for sp in species_list:
        thermo = sp.thermo
        tmin = getattr(thermo, "min_temp", None)
        tmax = getattr(thermo, "max_temp", None)
        out.append((sp.name, tmin, tmax))
    return out

def limiting_species(species_list):
    limits = species_temp_limits(species_list)
    limits = [x for x in limits if x[2] is not None]
    return min(limits, key=lambda x: x[2])

def name_matches_patterns(name, patterns):
    u = name.upper()
    return any(p.upper() in u for p in patterns)

def guess_pah_species(species_names, patterns, seed_remove):
    guessed = set(seed_remove)
    for name in species_names:
        if name_matches_patterns(name, patterns):
            guessed.add(name)
    return guessed

def load_species(input_file):
    return ct.Species.list_from_file(input_file)

def build_solution_from_species_and_reactions(name, species, reactions):
    return ct.Solution(
        name=name,
        thermo="ideal-gas",
        kinetics="gas",
        species=species,
        reactions=reactions
    )

def filter_reactions_by_species(input_file, kept_species):
    kept_names = {sp.name for sp in kept_species}

    tmp = ct.Solution(
        thermo="ideal-gas",
        kinetics="gas",
        species=kept_species,
        reactions=[]
    )

    all_rxns = ct.Reaction.list_from_file(input_file, tmp)

    def keep_rxn(rxn):
        participants = set(rxn.reactants) | set(rxn.products)
        return participants.issubset(kept_names)

    return [rxn for rxn in all_rxns if keep_rxn(rxn)]

def trim_mechanism(input_file, output_file, remove_species):
    all_species = load_species(input_file)
    kept_species = [sp for sp in all_species if sp.name not in remove_species]
    removed_species = sorted(sp.name for sp in all_species if sp.name in remove_species)

    reactions = filter_reactions_by_species(input_file, kept_species)

    gas = build_solution_from_species_and_reactions(
        name=Path(output_file).stem,
        species=kept_species,
        reactions=reactions
    )
    gas.write_yaml(output_file)

    return gas, removed_species

def print_low_tmax_species(species_list, threshold=2500.0):
    low = []
    for name, tmin, tmax in species_temp_limits(species_list):
        if tmax is not None and tmax <= threshold:
            low.append((name, tmin, tmax))
    low.sort(key=lambda x: x[2])
    if low:
        print(f"\nSpecies with Tmax <= {threshold:g} K:")
        for name, tmin, tmax in low:
            print(f"  {name:20s} Tmin={tmin:7.1f} K   Tmax={tmax:7.1f} K")
    else:
        print(f"\nNo species with Tmax <= {threshold:g} K found.")

def iterative_trim(input_file, output_file, target_tmax=3000.0, threshold_report=2500.0):
    all_species = load_species(input_file)
    all_names = [sp.name for sp in all_species]

    remove_species = guess_pah_species(all_names, PATTERNS, SEED_REMOVE)

    print("Initial guessed PAH/aromatic species to remove:")
    for name in sorted(remove_species):
        print(" ", name)

    gas, removed = trim_mechanism(input_file, output_file, remove_species)

    print("\nAfter first trim:")
    print(f"  species:   {gas.n_species}")
    print(f"  reactions: {gas.n_reactions}")
    print(f"  phase Tmin/Tmax = {gas.min_temp:.1f} / {gas.max_temp:.1f} K")
    print(f"  removed species count = {len(removed)}")

    print_low_tmax_species(gas.species(), threshold_report)

    # Iteratively remove the current limiting species if still below target
    extra_removed = []
    while gas.max_temp < target_tmax:
        lim_name, lim_tmin, lim_tmax = limiting_species(gas.species())
        print(f"\nCurrent limiting species: {lim_name} ({lim_tmin:.1f} - {lim_tmax:.1f} K)")

        # Stop if limiting species no longer looks like aromatic chemistry
        # so you don't accidentally gut core combustion species.
        if not name_matches_patterns(lim_name, PATTERNS) and lim_name not in SEED_REMOVE:
            print("Stopping: limiting species no longer matches PAH/aromatic patterns.")
            break

        remove_species.add(lim_name)
        extra_removed.append(lim_name)

        gas, removed = trim_mechanism(input_file, output_file, remove_species)

        print(f"Re-trimmed after removing {lim_name}")
        print(f"  species:   {gas.n_species}")
        print(f"  reactions: {gas.n_reactions}")
        print(f"  phase Tmin/Tmax = {gas.min_temp:.1f} / {gas.max_temp:.1f} K")

        print_low_tmax_species(gas.species(), threshold_report)

    print("\nFinal output:", output_file)
    print("Final phase Tmin/Tmax:", gas.min_temp, gas.max_temp)
    print("Total removed species:", len(remove_species))
    if extra_removed:
        print("Additional limiting species removed during iteration:", extra_removed)

    return gas, sorted(remove_species)

if __name__ == "__main__":
    gas, removed = iterative_trim(
        input_file=INPUT,
        output_file=OUTPUT,
        target_tmax=3000.0,
        threshold_report=2500.0
    )

    print("\nRemoved species:")
    for name in removed:
        print(" ", name)