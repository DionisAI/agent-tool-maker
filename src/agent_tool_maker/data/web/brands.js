'use strict';
// The registry contains reviewed, bundled image bytes; provider data is never a URL.
(() => {
  const icons=window.ATM_BRAND_DATA;
  if (!icons) throw new Error('ATM brand assets are missing. Reopen the updated console.');
  for (const value of Object.values(icons)) Object.freeze(value);
  Object.freeze(icons);
  const aliases=Object.freeze({
    codex:'openai', claude_code:'claude', ffprobe:'ffmpeg', chrome_devtools:'chrome',
    cloudflare_dns:'cloudflare', cloudflare_wrangler:'cloudflare', cloudflared:'cloudflare',
    expo_eas:'expo', eas:'expo', github_cli:'github', gh:'github', gltf_transform:'gltf',
    google_oauth:'google', google_trends:'google', gws:'google', itch_butler:'itch', butler:'itch',
    shopify_admin:'shopify', shopify_cli:'shopify', tiktok_posting:'tiktok',
    whisper_cpp:'openai', youtube_analytics:'youtube', youtube_data:'youtube',
  });
  const names=Object.freeze({
    apify:'Apify', clo:'CLO', dataforseo:'DataForSEO', firecrawl:'Firecrawl',
    marvelous_designer:'Marvelous Designer', opencli:'OpenCLI', spline:'Spline',
    tally:'Tally', xyq:'小云雀', local:'本地工具', studio:'Studio',
    playwright:'Playwright', printful:'Printful', remotion:'Remotion', imagemagick:'ImageMagick', itch:'itch.io',
  });
  function get(provider,toolId='') {
    const original=typeof provider==='string'?provider.trim():'';
    const normalized=original.toLowerCase();
    let key=Object.hasOwn(aliases,normalized)?aliases[normalized]:normalized;
    // Studio/local are generic extension namespaces, not globally Tripo brands.
    if (['studio','local'].includes(normalized) && /^tripo\.(studio|server)\./.test(toolId)) key='tripo';
    const icon=Object.hasOwn(icons,key)?icons[key]:null;
    const name=icon?.name || (Object.hasOwn(names,key)?names[key]:original) || '自定义工具';
    const words=name.split(/[\s._-]+/).filter(Boolean);
    const initials=(words.length>1?words.slice(0,2).map(x=>Array.from(x)[0]).join(''):Array.from(name).slice(0,2).join('')).toUpperCase();
    return Object.freeze({key,name,initials,src:icon?.src || null});
  }
  window.ATM_BRANDS=Object.freeze({get});
})();
