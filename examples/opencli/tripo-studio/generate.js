import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors';
import { StudioError } from './core.mjs';
import { generate, checkPaidPin } from './paid.mjs';

cli({ site: 'tripo-studio', name: 'generate', access: 'write',
  description: 'Submit one explicitly approved PRIVATE text-to-3D generation using Studio credits; durable no-retry claim',
  domain: 'studio.tripo3d.ai', strategy: Strategy.UI, browser: true, siteSession: 'persistent', navigateBefore: false,
  args: [
    { name: 'pin', type: 'string', default: '', help: 'Required reviewed paid-adapter digest' },
    { name: 'prompt', type: 'string', default: '', help: 'Approved text prompt, 1-1000 characters' },
    { name: 'budget', type: 'int', default: 0, help: 'Explicit Studio credit ceiling' },
    { name: 'quote', type: 'string', default: '', help: 'Approved visible quote digest' },
    { name: 'key', type: 'string', default: '', help: 'Stable request key; never change to evade uncertainty' },
    { name: 'ledger', type: 'string', default: '', help: 'Exact approved project path; nonsecret receipts only' },
    { name: 'confirm', type: 'bool', default: false, help: 'Set only after human approval of this task and quote' },
  ],
  columns: ['status', 'fingerprint', 'request_key', 'quote_sha256', 'max_credits', 'paid_submitted', 'created_at', 'quoted_credits', 'asset_id', 'acceptance', 'reused'],
  func: async (page, args) => {
    try { checkPaidPin(args.pin); return await generate(page, args); }
    catch (error) {
      if (!(error instanceof StudioError)) throw new CommandExecutionError('Tripo paid bridge failed. Inspect receipts before any retry.');
      if (error.code === 'login_required') throw new AuthRequiredError('studio.tripo3d.ai', error.message);
      if (error.code === 'invalid_argument' || error.code === 'confirmation_required') throw new ArgumentError(error.code + ': ' + error.message);
      throw new CommandExecutionError(error.code + ': ' + error.message);
    }
  },
});
