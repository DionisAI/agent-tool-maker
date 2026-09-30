import bpy,json,sys
path=sys.argv[sys.argv.index('--')+1]
with open(path,'w',encoding='utf-8') as f:
 json.dump({'objects':[{'name':o.name,'type':o.type} for o in bpy.data.objects],
            'meshes':len(bpy.data.meshes),'materials':len(bpy.data.materials),
            'blender_version':bpy.app.version_string,'validation':'scene_inventory_only'},f)
