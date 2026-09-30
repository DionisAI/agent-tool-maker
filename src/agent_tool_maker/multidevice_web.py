"""Bounded owner-console operations; never routed through agent bearer grants."""
import hashlib
from pathlib import Path
from .errors import RouterError
from .storage import canonical
from .sync import Sync


def read(router, path):
    if path == '/api/sync': return Sync(router.vault).status()
    if path == '/api/access':
        from .broker import list_grants
        return {**list_grants(router.state), 'broker':router.state.setting('broker_status')}
    raise RouterError('not_found','Unknown multi-device endpoint.')


def mutate(router, path, body, *, user_home=None):
    from .webapp import fields, text, flag, selections
    sync=Sync(router.vault)
    if path=='/api/sync/init':
        fields(body,('name',),('passphrase',))
        return sync.initialize(text(body,'name',limit=80))
    if path=='/api/sync/trust':
        fields(body,('card','fingerprint'),('send','receive','apply','replace','passphrase'))
        return sync.trust(body['card'],text(body,'fingerprint'),send=selections(body,'send') or [],receive=selections(body,'receive') or [],apply=flag(body,'apply'),replace=flag(body,'replace'))
    if path=='/api/sync/revoke':
        fields(body,('device','confirm'))
        if text(body,'device')!=text(body,'confirm'): raise RouterError('approval_required','Confirm the device fingerprint.')
        return sync.revoke(text(body,'device'),apply=True)
    if path=='/api/sync/export':
        fields(body,('device',),('passphrase',))
        return {'encrypted_packet':sync.export_packet(text(body,'device')),'plaintext_returned':False}
    if path=='/api/sync/import':
        fields(body,('packet',),('apply','passphrase'))
        return sync.import_packet(body['packet'],apply=flag(body,'apply'))
    if path=='/api/sync/resolve':
        fields(body,('provider','choose','expected'),('apply','passphrase'))
        return sync.resolve(text(body,'provider'),text(body,'choose'),text(body,'expected'),apply=flag(body,'apply'))
    if path=='/api/access/revoke':
        from .broker import revoke
        fields(body,('id','confirm'))
        if text(body,'id')!=text(body,'confirm'):raise RouterError('approval_required','Confirm the grant ID.')
        return revoke(router.state,text(body,'id'),apply=True)
    if path=='/api/access/grant':
        from .broker import grant
        fields(body,('agent','tools','workspace'),('permissions','allow_paid','ttl_hours','apply','approved_sha256'))
        agent=text(body,'agent')
        if agent not in {'claude','codex'}:raise RouterError('invalid_agent','Select Claude or Codex.')
        kwargs=dict(tools=selections(body,'tools') or [],workspace=Path(text(body,'workspace')),
                    grants=selections(body,'permissions',{'external_write','production','execute_code'}) or [],
                    ttl_hours=body.get('ttl_hours',168),allow_paid=flag(body,'allow_paid'),user_home=user_home)
        plan=grant(router,agent,**kwargs)
        digest=hashlib.sha256(canonical(plan).encode()).hexdigest()
        if not flag(body,'apply'):return {**plan,'approval_sha256':digest}
        if text(body,'approved_sha256')!=digest:raise RouterError('plan_changed','Review the exact current grant before applying.')
        return grant(router,agent,**kwargs,apply=True)
    raise RouterError('not_found','Unknown multi-device operation.')
