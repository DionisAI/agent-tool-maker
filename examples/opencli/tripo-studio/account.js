import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors';
import { account, checkPin, StudioError } from './core.mjs';

cli({
  site: 'tripo-studio', name: 'account', access: 'read',
  description: 'Read Tripo Studio login and subscription credits from visible DOM; no API key or paid call',
  domain: 'studio.tripo3d.ai', strategy: Strategy.UI, browser: true,
  siteSession: 'persistent', navigateBefore: false,
  args: [{ name: 'pin', type: 'string', default: '', help: 'ATM-reviewed adapter bundle digest' }],
  columns: ['status', 'logged_in', 'credits', 'billing', 'source', 'secrets_returned', 'paid_submitted'],
  func: async (page, args) => {
    try { checkPin(args.pin); return await account(page); }
    catch (error) {
      if (!(error instanceof StudioError)) throw new CommandExecutionError('Tripo browser bridge failed; no paid call was attempted.');
      if (error.code === 'login_required') throw new AuthRequiredError('studio.tripo3d.ai', error.message);
      if (error.code === 'invalid_argument') throw new ArgumentError(error.message);
      throw new CommandExecutionError(error.code + ': ' + error.message);
    }
  },
});
