# protein_WaterStructure_HydrophobicityModel

Use water structure analysis to color your protein based on predicted dewetting free energy (using Sam Lobo & Saeed Najafi's hydrophobicity model) and water triplet distribution principal component contributions (from Dennis Robinson and Sally Jiao's work modelling small hydrophobes).  
  
This analysis takes <25 min of computation for a 100 residue protein, including ~20 min on a GPU (NVIDIA V100) and <3min on parallel CPUs (Intel Xeon Gold 6148 with 1 thread per solvated residue / custom group). This can be reduced depending on your error bar tolerance.  

---

### **Input:**
- pdb file of just protein (no water or ions)  

### **Output:**
- pdb file with dewetting free energy predictions of each residue (or custom group) listed in the tempfactor column
- 3 pdb files with the 3 principal component contributions of each residue (or custom group) listed in the tempfactor column
- csv file with triplet distribution for each residue (or custom group), histograms and plots of dewetting free energy predictions & principal componenet contributions, and many txt files of raw data triplet angles  

### **Tutorial:**
[Click here](https://roamresearch.com/#/app/SamLobo/page/P2_MRPX_6) for the complete tutorial on Sam Lobo's Roam page which includes detailed install instructions, the commands necessary for each step in the procedure, some background info, and FAQs (e.g. "How can I get this working on my cluster?").

---

## Procedure summary:

1. Use GROMACS to ***build your system***: protein + water + ions
2. Use OpenMM to ***run a short MD simulation*** (GPU recommended)
3. ***Measure water angles*** around each residue/group (parallel CPUs recommended)
4. ***Process water angles***, and ***output pdbs*** with stored dewetting free energy predictions and principal component contributions
5. **Color pdbs** by dewetting free energy and principal component contributions

You can skip steps 1 & 2 if you already have a simulation to analyze.  

---

## Install requirements:

1. [Anaconda](https://www.anaconda.com/download) or miniconda for python tools
2. [GROMACS](https://manual.gromacs.org/documentation/current/install-guide/index.html) (Step 1)
3. [OpenMM](http://docs.openmm.org/latest/userguide/application/01_getting_started.html#installing-openmm) (Step 2) - you need to fix for TIP4P water constraints and you may need to install CUDA drivers depending on your architecture
4. Fortran compiler (Step 3) - anaconda's f2py should work (see tutorial's FAQs)
5. [MDAnalysis](https://www.mdanalysis.org/pages/installation_quick_start/) (Step 3 & 4)
6. [ChimeraX](https://www.cgl.ucsf.edu/chimerax/download.html) or [Pymol](https://pymol.org/2/) (recommended for Step 5)
See [tutorial](https://roamresearch.com/#/app/SamLobo/page/P2_MRPX_6) for more install instructions.

---

## Main Code:  
- **process_with_gromacs.sh**
  - Usage: `bash process_with_gromacs.sh <protein[.pdb]>`
  - Executes some basic gromacs commands to build your system: '\<protein\>_processed.gro'
  - Creates a topology file (topol.top), solvates your system, and adds neutralizing ions.
- **simulate_with_openmm.py**
  - Example usage:  
    `python simulate_with_openmm.py <protein[_processed.gro]>`  run a short NPT simulation  
    `python simulate_with_openmm.py myProtein_processed.gro --restrain` keep heavy atoms on protein restrained    
    `python simulate_with_openmm.py myProtein_processed.gro --restrain -ns 2`  also run a 2 ns simulation (default is 5 ns)
  - 
- water_triplets/**triplet.py**
  - Example usage:  
    `python triplet.py <protein[_processed.gro]> <trajectory> -res <int>` to analyze one residue  
    `python triplet.py myProtein_processed.gro traj.dcd -res 10 -ch B` to analyze the resid 10 on chain B  
    `python triplet.py myProtein_processed.gro traj.dcd --groupsFile groups_file.txt --groupNum 20` to analyze the group described by MDAnalysis selection string in the 20th line of groups_file.txt  
    `python triplet.py protein[_processed.gro traj.dcd -res 10 --hydrationCutoff 6 --time 1` to define hydration waters as being 6 Angstroms (default is 4.25A) around resid 10's heavy atoms, and to analyze just the last 1 ns (default is 5 ns) of the trajectory   
  - 
- water_triplets/**process_angles.py**
  - Example usage:  
    `python process_angles.py <protein[.pdb]>`  
    `python process_angles.py myProtein.pdb --multiChain` use when your protein has multiple chains  
    `python process_angles.py myProtein.pdb --groupsFile groups_file.txt` use when you created custom groups to analyze  
  - 
- water_triplets/**analyze_groups.py**
  - Usage: `python analyze_groups.py <protein[.pdb]>`
  - 

## Supporting Code:
- remove_checkpointed_duplicates.py
  - Called by simulate_with_openmm.py when a simulation is restarted from a checkpoint in order to clean up duplicate frames.
- water_triplets/water_properties.py
  - Called by triplet.py to measure water angles
- water_triplets/waterlib.f90
  - Called by water_properties.py to efficiently measure water angles
- water_triplets/convert_triplets.py
  - Called by analyze_groups.py to convert water triplet distributions to dewetting free energy predictions and principal component contributions.
- water_triplets/principalComps.csv
  - Read by convert_triplets.py 
- water_triplets/bulk_water_triplets.csv
  - Read by convert_triplets.py
    
---

## Code specifically for UCSB's Pod Cluster (SLURM scheduler):  
- **submit_simulation.py**
  - Usage: `python submit_simulation.py <protein[_processed.gro]>`
  - Uses *simulate_with_openmm.py* to submit a GPU job (Step 2)
- **submit_triplets.py**
  - Usage: `python submit_triplets.py <protein[.pdb]> <trajectory>`
  - Uses *triplet.py* and srun to parallelize and submit many CPU jobs, 1 per solvated residue/group (Step 3)
- **full_hydrophobicity_procedure.sh**
  - Usage: `sbatch full_hydrophobicity_procedure <protein_name>`
  - Manages and submits all SLURM jobs and analysis (Steps 1-4).  
    Designed so that this single sbatch command can fully process your protein & output colored pdbs.
  - Calls *process_with_gromacs.sh*, *submit_simulation.sh*, *submit_triplets.py*, *process_angles.py*, and *analyze_groups.py*
