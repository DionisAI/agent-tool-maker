import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors';
import { assets, checkPin, StudioError } from './core.mjs';

cli({
  site: 'tripo-studio', name: 'assets', access: 'read',
  description: 'List currently loaded Tripo Studio model cards without signed links or private account data',
  domain: 'studio.tripo3d.ai', strategy: Strategy.UI, browser: true,
  siteSession: 'persistent', navigateBefore: false,
  args: [
    { name: 'limit', type: 'int', default: 20, help: 'Maximum returned loaded model cards (1-100); not full pagination' },
    { name: 'pin', type: 'string', default: '', help: 'ATM-reviewed adapter bundle digest' },
  ],
  columns: ['status', 'assets', 'returned_count', 'loaded_count', 'coverage', 'all_assets', 'secrets_returned', 'paid_submitted'],
  func: async (page, args) => {
    try { checkPin(args.pin); return await assets(page, args.limit); }
    catch (error) {
      if (!(error instanceof StudioError)) throw new CommandExecutionError('Tripo browser bridge failed; no paid call was attempted.');
      if (error.code === 'login_required') throw new AuthRequiredError('studio.tripo3d.ai', error.message);
      if (error.code === 'invalid_argument') throw new ArgumentError(error.message);
      throw new CommandExecutionError(error.code + ': ' + error.message);
    }
  },
});
