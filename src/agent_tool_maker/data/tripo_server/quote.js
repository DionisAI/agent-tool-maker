import { cli, Strategy } from '@jackwener/opencli/registry';
import { AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors';
import { StudioError } from './core.mjs';
import { quote, checkPaidPin } from './paid.mjs';

cli({ site: 'tripo-studio', name: 'quote', access: 'read',
  description: 'Inspect current text-generation Studio credit quote; switches text mode but never submits',
  domain: 'studio.tripo3d.ai', strategy: Strategy.UI, browser: true, siteSession: 'persistent', navigateBefore: false,
  args: [{ name: 'pin', type: 'string', default: '', help: 'Required reviewed paid-adapter digest' }],
  columns: ['status', 'credits', 'quoted_credits', 'model', 'privacy', 'parts_enabled', 'texture_8k_enabled', 'quote_sha256', 'billing', 'paid_submitted'],
  func: async (page, args) => {
    try { checkPaidPin(args.pin); return await quote(page); }
    catch (error) {
      if (error instanceof StudioError && error.code === 'login_required') throw new AuthRequiredError('studio.tripo3d.ai', error.message);
      throw new CommandExecutionError(error instanceof StudioError ? error.code + ': ' + error.message : 'Tripo quote bridge failed; no Generate click.');
    }
  },
});
