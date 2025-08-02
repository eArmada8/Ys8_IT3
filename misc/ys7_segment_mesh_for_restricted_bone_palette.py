# Tool to segment meshes for Ys VII/MoC models, which cannot accept more than 4 bones per mesh.
# Usage:  Run by itself without commandline arguments and it will open meshes (with intact vgmaps)
# and save the segmented meshes in a folder.
#
# For command line options, run:
# /path/to/python3 ys7_segment_mesh_for_restricted_bone_palette.py --help
#
# Requires lib_fmtibvb.py, put in the same directory
#
# GitHub eArmada8/Ys8_IT3

try:
    import typing, math, json, glob, os, sys
    from lib_fmtibvb import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

#Thank you to github.com/Kyuuhachi for the bin pack code and its optimization algorithm
fsi = frozenset[int]

def maximal_connected_unions(sets: set[fsi], max: int) -> set[fsi]:
	def inner(sets: list[fsi], current: fsi) -> typing.Iterable[fsi]:
		yielded = False
		for i in range(len(sets)):
			if not current & sets[i]:
				continue
			u = current | sets[i]
			if len(current) < len(u) <= max:
				yield from inner(sets[i+1:], u)
				yielded = True
		if not yielded:
			yield current
	ss = sorted(sets, key=len, reverse=True)
	return set(inner(ss[1:], ss[0]))

def optimize_first(sets: typing.Iterable[fsi], size: int) -> typing.Iterable[fsi]:
	sets = set(sets)
	# Removing subsets neither helps nor hinders performance, but it improves the cost heuristic
	sets -= { x for x in sets for y in sets if x < y }
	while sets:
		candidates = maximal_connected_unions(sets, size)
		best, covered = max([
			(cand, { x for x in sets if x <= cand })
			for cand in candidates
		], key=lambda x: len(x[1]))
		yield best
		sets -= covered

def pack_bins(sets: list[fsi], size: int) -> typing.Iterable[fsi]:
	# Greedy bin packing algorithm. Not optimal, but fast.
	while sets:
		bin = fsi()
		for s in sorted(sets, key=len, reverse=True):
			if len(bin | s) <= size:
				bin |= s
				sets.remove(s)
		yield bin

def optimize(sets: typing.Iterable[fsi], size: int) -> typing.Iterable[fsi]:
	return pack_bins(list(optimize_first(sets, size)), size)

def optimal_vertex_group_segments(all_group_sets, size = 4):
    return [tuple(x) for x in list(optimize({fsi(x) for x in all_group_sets}, size = size))]

def segment_mesh (mesh_filename, max_group = 4, clean_vg_indices = True):
    fmt = read_fmt(mesh_filename+'.fmt')
    ib = read_ib(mesh_filename+'.ib',fmt)
    vb = read_vb(mesh_filename+'.vb',fmt)
    vgmap = json.loads(open(mesh_filename+'.vgmap').read())
    semantics = [x['SemanticName'] for x in vb]
    if 'BLENDINDICES' in semantics:
        if 'BLENDWEIGHTS' in semantics:
            blendwt = semantics.index('BLENDWEIGHTS')
        else:
            blendwt = semantics.index('BLENDWEIGHT')
        blendidx = semantics.index('BLENDINDICES')
        palettes = []
        for i in range(len(ib)):
            tri_indices = sorted(list(set([x for y in [\
                [vb[blendidx]['Buffer'][j][k] for k in range(4) if vb[blendwt]['Buffer'][j][k] > 0.0000001]\
                for j in ib[i]] for x in y])))
            palettes.append(tri_indices)

        # Determine the bone palettes to be used for segmentation
        pal_sets = sorted(list(set([tuple(x) for x in palettes])))
        problem_sets_present = False
        if any([len(x) > max_group for x in pal_sets]):
            print("Some triangles have too many groups to properly segment!")
            print("Unsegmentable triangles will be in {0}/{0}_unusable.vb.".format(mesh_filename))
            print("Please repair the affected vertices *in the original mesh* and run this script again.")
            input("Press Enter to continue.")
            problem_sets_present = True
            broken_pal_sets = [x for x in pal_sets if len(x) > max_group]
            pal_sets = [x for x in pal_sets if len(x) <= max_group]
        new_pal_sets = optimal_vertex_group_segments(pal_sets, max_group)
        if problem_sets_present == True:
            # The final group will be a fully inclusive palette, used to collect broken triangles
            new_pal_sets.append(tuple(sorted(list(set([x for y in vb[blendidx]['Buffer'] for x in y])))))

        # Determine which palette each triangle will use
        pal_to_use = [[i for i in range(len(new_pal_sets)) if set(palettes[j]).issubset(new_pal_sets[i])][0] for j in range(len(palettes))]
        triangles_by_pal = {j:[i for i in range(len(pal_to_use)) if pal_to_use[i] == j] for j in range(len(new_pal_sets))}
        vgmap_by_pal = {j:{k:vgmap[k] for k in vgmap if vgmap[k] in new_pal_sets[j]} for j in range(len(new_pal_sets))}
        for i in range(len(new_pal_sets)):
            vertices = sorted(list(set([x for y in [ib[z] for z in triangles_by_pal[i]] for x in y])))
            reverse_vert_map = {vertices[j]:j for j in range(len(vertices))}
            new_vb = []
            for j in range(len(vb)):
                new_buffer = [vb[j]['Buffer'][k] for k in range(len(vb[j]['Buffer'])) if k in vertices]
                new_vb.append({'Buffer':new_buffer})
            if clean_vg_indices == True: # Remove group assignments for empty weights
                new_vb[blendidx]['Buffer'] = [[y if y in vgmap_by_pal[i].values() else 0 for y in x]\
                    for x in new_vb[blendidx]['Buffer']]
            new_ib = [[reverse_vert_map[y] for y in ib[x]] for x in triangles_by_pal[i]]
            if not (os.path.exists(mesh_filename) and os.path.isdir(mesh_filename)):
                os.mkdir(mesh_filename)
            submesh_filename = "{0}/{0}_{1:02d}".format(mesh_filename, i)
            if problem_sets_present == True and i == (len(new_pal_sets) - 1):
                submesh_filename = "{0}/{0}_unusable".format(mesh_filename)
            write_fmt(fmt, submesh_filename + '.fmt')
            write_ib(new_ib, submesh_filename + '.ib', fmt)
            write_vb(new_vb, submesh_filename + '.vb', fmt)
            open(submesh_filename + '.vgmap', 'wb').write(json.dumps(vgmap_by_pal[i],indent=4).encode())
    return True

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('mesh_vb_filename', help="Name of mesh .vb file to split (required).")
        args = parser.parse_args()
        if os.path.exists(args.mesh_vb_filename) and args.mesh_vb_filename[-3:].lower() == '.vb':
            mesh_filename = args.mesh_vb_filename[:-3]
            if os.path.exists(mesh_filename+'.fmt')\
                and os.path.exists(mesh_filename+'.ib')\
                and os.path.exists(mesh_filename+'.vgmap'): 
                segment_mesh(mesh_filename)
    else:
        mesh_files = glob.glob('*.vb')
        for i in range(len(mesh_files)):
            mesh_filename = mesh_files[i][:-3]
            if os.path.exists(mesh_filename+'.fmt')\
                and os.path.exists(mesh_filename+'.ib')\
                and os.path.exists(mesh_filename+'.vgmap'): 
                print("Processing {}...".format(mesh_filename))
                segment_mesh(mesh_filename)
