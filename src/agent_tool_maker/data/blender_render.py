import bpy,sys
scene=bpy.context.scene
scene.render.image_settings.file_format='PNG'
scene.render.filepath=sys.argv[sys.argv.index('--')+1]
scene.render.resolution_percentage=100
bpy.ops.render.render(write_still=True)
