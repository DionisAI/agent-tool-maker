import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors';
import { StudioError } from './core.mjs';
import { checkExtendedPin, inspectAsset, resolveAsset, assetsAll, operationQuote, executePaid, imageQuote, generateImage, exportQuote, exportModel } from './extended.mjs';

const pin = { name: 'pin', type: 'string', default: '', help: 'Required reviewed extended adapter digest' };
const asset = { name: 'asset', type: 'string', default: '', help: 'Actual asset UUID, not thumbnail preview task UUID' };
const settings = { name: 'settings', type: 'string', default: '{}', help: 'Reviewed operation-specific settings JSON; never arbitrary selectors' };
const execution = [
  { name: 'quote', type: 'string', default: '', help: 'Approved current quote SHA256' },
  { name: 'key', type: 'string', default: '', help: 'Stable request key, identical in ATM and input' },
  { name: 'ledger', type: 'string', default: '', help: 'Exact approved project path; nonsecret receipts only' },
  { name: 'confirm', type: 'bool', default: false, help: 'Only after explicit approval of the exact operation and source' },
];
const budget = { name: 'budget', type: 'int', default: 0, help: 'Approved Studio credit ceiling, 1-10000' };
const definitions = [
  ['asset', 'read', 'Inspect or wait for visible model completion, mesh counts and export readiness', [asset, { name: 'wait', type: 'int', default: 0, help: 'Wait for model completion up to 120 seconds' }], inspectAsset],
  ['asset-resolve', 'read', 'Resolve a visible thumbnail preview UUID to its actual asset UUID without guessing', [{ name: 'preview', type: 'string', default: '', help: 'Preview task UUID from an asset card' }], resolveAsset],
  ['assets-all', 'read', 'Automatically scroll model assets with explicit pagination bounds and honest completion coverage', [{ name: 'limit', type: 'int', default: 1000, help: 'Maximum returned cards 1-1000' }, { name: 'pages', type: 'int', default: 50, help: 'Maximum scroll rounds 1-50' }], assetsAll],
  ['retopo-quote', 'write', 'Prepare reviewed retopology settings and read price; never submit', [asset, settings], (page,args) => operationQuote(page,{...args,operation:'retopo'})],
  ['retopo', 'write', 'Submit one confirmed budget-bounded retopology with a durable no-retry receipt', [asset, ...execution, budget], (page,args) => executePaid(page,{...args,operation:'retopo'})],
  ['rig-quote', 'write', 'Prepare humanoid/other and skeleton settings and read Auto Rig quote; never submit', [asset, settings], (page,args) => operationQuote(page,{...args,operation:'rig'})],
  ['rig', 'write', 'Submit one confirmed Auto Rig after quote and asset checks; no automatic retry', [asset, ...execution, budget], (page,args) => executePaid(page,{...args,operation:'rig'})],
  ['image-quote', 'write', 'Upload one explicitly approved project image and quote PRIVATE image-to-3D; no generation', [{ name: 'file', type: 'string', default: '', help: 'Explicit project PNG/JPEG/WEBP up to 20MiB' }, ...execution.filter(arg => arg.name !== 'quote')], imageQuote],
  ['image-generate', 'write', 'Submit one approved PRIVATE image-to-3D using unchanged uploaded quote and credit ceiling', [...execution, budget, { name: 'image-sha', type: 'string', default: '', help: 'Image SHA256 from image-quote' }], (page,args) => generateImage(page,{...args,image_sha:args['image-sha']})],
  ['export-quote', 'write', 'Open completed asset GLB export dialog and inspect current texture settings; no download', [asset], exportQuote],
  ['export', 'write', 'Download completed subscribed GLB, validate header/JSON/mesh and deliver a local artifact', [asset, ...execution, { name: 'output', type: 'string', default: '', help: 'New project-local model.glb destination' }], exportModel],
];
for (const [name, access, description, args, run] of definitions) {
  cli({ site:'tripo-studio', name, access, description, domain:'studio.tripo3d.ai', strategy:Strategy.UI,
    browser:true, siteSession:'persistent', navigateBefore:false, args:[pin,...args], columns:['result'],
    func:async (page,inputs) => {
      try { checkExtendedPin(inputs.pin); return (await run(page,inputs)).map(result => ({ result })); }
      catch (error) {
        if (!(error instanceof StudioError)) throw new CommandExecutionError('Tripo extended bridge failed. Retain receipts and inspect before retry.');
        if (error.code === 'login_required') throw new AuthRequiredError('studio.tripo3d.ai',error.message);
        if (['invalid_argument','confirmation_required'].includes(error.code)) throw new ArgumentError(error.code+': '+error.message);
        throw new CommandExecutionError(error.code+': '+error.message);
      }
    },
  });
}
