// Samples, loops and AI tools: asked on every upload and in the Vault (Brief 25b D1, F;
// Agreement 3.6 and 9.1(e)). Pure helpers, shared by SongForm and the Vault.
import {
  AI_TOOLS_DETAIL_MAX, LOOP_LICENSE_MAX_BYTES, LOOP_LICENSE_TYPES, MAX_LOOPS,
} from '../sync/constants';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export const emptyLoop = () => ({ creator_name: '', creator_email: '', source: '', loop_name: '', file: null });

export const EMPTY_DECLARATIONS = {
  samples: '',
  samples_attested: false,
  loops: [],
  ai_tools: '',
  ai_tools_detail: '',
  ai_tools_attested: false,
};

export const usesLoops = (d) => d.samples === 'royalty_free_loop';

export const licenseFileProblem = (file) => {
  if (!file) return null;
  if (!LOOP_LICENSE_TYPES.includes(file.type)) return 'Upload the license as a PDF, PNG or JPG.';
  if (file.size > LOOP_LICENSE_MAX_BYTES) return 'The license file must be 10 MB or smaller.';
  return null;
};

// What is still missing, as short phrases. rightsEmails: lower-cased emails in the splits
// (null skips the loop-creator check, e.g. in the Vault where the server checks it).
export const declarationsMissing = (d, { rightsEmails = null, requireFiles = false } = {}) => {
  const missing = [];
  if (!d.samples) missing.push('samples answer');
  else if (d.samples === 'sample') missing.push('a song without samples');
  else if (!d.samples_attested) missing.push('samples confirmation');
  if (usesLoops(d)) {
    if (d.loops.length < 1 || d.loops.length > MAX_LOOPS) missing.push('your loops');
    d.loops.forEach((lp, i) => {
      if (!lp.creator_name.trim() || !lp.loop_name.trim() || !lp.source || !EMAIL_RE.test(lp.creator_email.trim())) {
        missing.push(`loop ${i + 1} details`);
      } else if (rightsEmails && !rightsEmails.includes(lp.creator_email.trim().toLowerCase())) {
        missing.push(`loop ${i + 1} creator in the splits`);
      }
      if (requireFiles && !lp.file) missing.push(`loop ${i + 1} license`);
      if (licenseFileProblem(lp.file)) missing.push(`loop ${i + 1} license file`);
    });
  }
  if (!d.ai_tools) missing.push('AI tools answer');
  else if (d.ai_tools === 'full') missing.push('a song made by people');
  else if (d.ai_tools === 'partial' && !d.ai_tools_detail.trim()) missing.push('which parts used AI');
  else if (d.ai_tools_detail.length > AI_TOOLS_DETAIL_MAX) missing.push('a shorter AI description');
  if (d.ai_tools && !d.ai_tools_attested) missing.push('AI tools confirmation');
  return missing;
};

export const buildDeclarationsPayload = (d) => ({
  samples: d.samples,
  samples_attested: d.samples_attested,
  loops: usesLoops(d) ? d.loops.map((lp) => ({
    creator_name: lp.creator_name.trim(), creator_email: lp.creator_email.trim().toLowerCase(),
    source: lp.source, loop_name: lp.loop_name.trim(),
  })) : [],
  ai_tools: d.ai_tools,
  ai_tools_detail: d.ai_tools === 'partial' ? d.ai_tools_detail.trim() : '',
  ai_tools_attested: d.ai_tools_attested,
});
