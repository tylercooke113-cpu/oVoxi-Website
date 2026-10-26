// The UI primitives import the "@/lib/utils" alias, which jest (unlike webpack) does not
// resolve. We only exercise pure logic here, so stub those modules out, as the existing
// SubscriptionTab test does with its heavy deps. The real rights/validation logic still runs.
jest.mock('../components/ui/input', () => ({ Input: 'input' }));
jest.mock('../components/ui/label', () => ({ Label: 'label' }));
jest.mock('../components/ui/checkbox', () => ({ Checkbox: 'input' }));
jest.mock('../components/ui/select', () => ({
  Select: 'div', SelectContent: 'div', SelectItem: 'div', SelectTrigger: 'div', SelectValue: 'div',
}));
jest.mock('../components/ui/radio-group', () => ({ RadioGroup: 'div', RadioGroupItem: 'div' }));

import { emptySong, carryOverSong, songMissing } from './SongForm';
import { emptyRights } from '../sync/RightsSection';
import { runBatch, TOO_MANY_MESSAGE } from './useBatchUpload';
import { EMPTY_DECLARATIONS, buildDeclarationsPayload, emptyLoop } from './declarations';
import { legalNameMismatch, writersMissingPro } from '../sync/RightsSection';
import { isIntakeValid, buildIntakePayload } from '../sync/SyncIntakeFields';

const ORIGINAL = { ...EMPTY_DECLARATIONS, samples: 'original', samples_attested: true,
  ai_tools: 'none', ai_tools_attested: true };
const LOOP = { creator_name: 'Jordan Producer', creator_email: 'jordan@example.com',
  source: 'Splice', loop_name: 'Dusty Keys', file: { name: 'l.pdf', type: 'application/pdf', size: 100 } };

// A song that passes every validation rule (owns everything, AI consent only).
const completeSong = (over = {}) => emptySong({
  form: { artist_name: 'Artist', track_name: 'Track', genre: 'Pop' },
  file: { name: 'track.wav', size: 1000 },
  moods: ['Chill'],
  vocals: 'vocal',
  bpm: '120',
  musicalKey: 'C major',
  consentAi: true,
  declarations: ORIGINAL,
  rights: { ...emptyRights(), owns_everything: true, self_legal_name: 'Real Name', attested: true },
  ...over,
});

// Manual splits with a co-writer who is also the loop creator.
const loopRights = (writerPro = true) => ({
  ...emptyRights(), self_legal_name: 'Real Name', attested: true,
  writers: [
    { legal_name: 'Real Name', pct: '50', role: 'CA', society: writerPro ? 'BMI' : '', ipi: writerPro ? '123456789' : '',
      email: '', no_publisher: false,
      publishers: [{ legal_name: 'Real Name', pct: '100', role: 'E', society: '', ipi: '', email: '' }] },
    { legal_name: 'Jordan Producer', pct: '50', role: 'C', society: writerPro ? 'ASCAP' : '', ipi: writerPro ? '123456789' : '',
      email: 'jordan@example.com', no_publisher: true, publishers: [] },
  ],
  master_owners: [{ legal_name: 'Real Name', pct: '100', role: null, society: '', ipi: '', email: '' }],
});
const SYNC_INTAKE = { distributor: 'DistroKid', content_id: 'no', pro_name: 'BMI', ipi: '123456789', sync_sole_attested: true };

// Collects patchSong calls into a final per-key state, like the real reducer would.
const makeRecorder = () => {
  const states = {};
  const patchSong = (key, partial) => {
    states[key] = { ...states[key], ...partial };
  };
  return { states, patchSong };
};

const err = (status, detail) => ({ response: { status, data: { detail } } });

describe('songMissing', () => {
  test('a complete song is missing nothing', () => {
    expect(songMissing(completeSong())).toEqual([]);
  });

  test('flags a missing audio file', () => {
    expect(songMissing(completeSong({ file: null }))).toContain('audio file');
  });

  test('requires sync details when sync consent is on', () => {
    const s = completeSong({ consentAi: false, consentSync: true });
    expect(songMissing(s)).toContain('sync details');
  });

  test('flags invalid splits', () => {
    const s = completeSong({
      rights: { ...emptyRights(), owns_everything: true, self_legal_name: 'Real Name', attested: false },
    });
    expect(songMissing(s)).toContain('splits');
  });

  test('BPM outside range is flagged unless unsure', () => {
    expect(songMissing(completeSong({ bpm: '999' }))).toContain('BPM');
    expect(songMissing(completeSong({ bpm: '', bpmUnsure: true }))).not.toContain('BPM');
  });
});

describe('carryOverSong', () => {
  test('copies only the fields listed in A3', () => {
    const prev = completeSong({
      form: { artist_name: 'Carry Me', track_name: 'Old Title', genre: 'Trap' },
      consentAi: true,
      consentSync: true,
      consentExclusive: true,
      intake: {
        distributor: 'DistroKid',
        content_id: 'no',
        pro_name: 'ASCAP',
        ipi: '123456789',
        sync_sole_attested: true,
      },
      rights: { ...emptyRights(), self_legal_name: 'Legal Name', legal_name_touched: true },
    });

    const next = carryOverSong(prev);

    // Carried over
    expect(next.form.artist_name).toBe('Carry Me');
    expect(next.consentAi).toBe(true);
    expect(next.consentSync).toBe(true);
    expect(next.consentExclusive).toBe(false);          // Oct 26: exclusive is a Vault switch only
    expect(next.intake.distributor).toBe('DistroKid');
    expect(next.intake.pro_name).toBe('ASCAP');
    expect(next.intake.ipi).toBe('123456789');
    expect(next.rights.self_legal_name).toBe('Legal Name');
    expect(next.rights.legal_name_touched).toBe(true);

    // Reset
    expect(next.form.track_name).toBe('');
    expect(next.form.genre).toBe('');
    expect(next.file).toBeNull();
    expect(next.declarations).toEqual(EMPTY_DECLARATIONS);       // song-specific answers reset
    expect(next.intake.sync_sole_attested).toBe(false);
    expect(next.intake.content_id).toBe('');
    expect(next.rights.owns_everything).toBe(false);
    expect(next.status).toBe('draft');
    expect(next.key).not.toBe(prev.key);
  });
});

describe('runBatch', () => {
  const getToken = async () => 'token';

  test('continues with the next song after one fails', async () => {
    const songs = [completeSong(), completeSong()];
    const { states, patchSong } = makeRecorder();

    let call = 0;
    const doUpload = async () => {
      call += 1;
      if (call === 1) throw new Error('network blip');
      return 'sub-2';
    };

    const { stopReason } = await runBatch(songs, { getToken, patchSong, doUpload });

    expect(stopReason).toBeNull();
    expect(states[songs[0].key].status).toBe('failed');
    expect(states[songs[1].key].status).toBe('received');
    expect(states[songs[1].key].submissionId).toBe('sub-2');
  });

  test('stops on the agreement 403 and resumes from queued/failed songs', async () => {
    const songs = [completeSong(), completeSong()];
    const { states, patchSong } = makeRecorder();

    // First pass: the agreement is not signed, so song 1 cannot be sent.
    const failUpload = async () => {
      throw err(403, 'Sign the Artist Agreement before uploading.');
    };
    const first = await runBatch(songs, { getToken, patchSong, doUpload: failUpload });

    expect(first.stopReason).toBe('agreement');
    expect(states[songs[0].key].status).toBe('queued'); // not sent, ready to resume
    expect(states[songs[1].key]).toBeUndefined();        // never touched

    // Resume: agreement signed, both songs go through.
    let n = 0;
    const okUpload = async () => { n += 1; return `sub-${n}`; };
    const second = await runBatch(songs, { getToken, patchSong, doUpload: okUpload });

    expect(second.stopReason).toBeNull();
    expect(states[songs[0].key].status).toBe('received');
    expect(states[songs[1].key].status).toBe('received');
  });

  test('marks the remaining songs with a clean message on the open-submissions cap', async () => {
    const songs = [completeSong(), completeSong()];
    const { states, patchSong } = makeRecorder();

    const capUpload = async () => { throw err(429, 'Too many uploads in progress'); };
    const { stopReason } = await runBatch(songs, { getToken, patchSong, doUpload: capUpload });

    expect(stopReason).toBe('too_many');
    expect(states[songs[0].key].status).toBe('failed');
    expect(states[songs[0].key].error).toBe(TOO_MANY_MESSAGE);
    expect(states[songs[1].key].status).toBe('failed');
    expect(states[songs[1].key].error).toBe(TOO_MANY_MESSAGE);
  });
});


describe('Brief 25b upload rules', () => {
  test('every upload answers samples and AI tools', () => {
    const m = songMissing(completeSong({ declarations: EMPTY_DECLARATIONS }));
    expect(m).toContain('samples answer');
    expect(m).toContain('AI tools answer');
  });

  test('a sample blocks the upload; mostly-AI blocks the upload', () => {
    expect(songMissing(completeSong({ declarations: { ...ORIGINAL, samples: 'sample' } })))
      .toContain('a song without samples');
    expect(songMissing(completeSong({ declarations: { ...ORIGINAL, ai_tools: 'full' } })))
      .toContain('a song made by people');
  });

  test('partial AI needs the parts and tool', () => {
    expect(songMissing(completeSong({ declarations: { ...ORIGINAL, ai_tools: 'partial' } })))
      .toContain('which parts used AI');
  });

  test('loop songs: sync only, creator in the splits, a license per loop', () => {
    const loops = { ...ORIGINAL, samples: 'royalty_free_loop', loops: [LOOP] };
    const ok = completeSong({ consentAi: false, consentSync: true, intake: SYNC_INTAKE,
      declarations: loops, rights: loopRights() });
    expect(songMissing(ok)).toEqual([]);
    expect(songMissing({ ...ok, consentAi: true })).toContain('AI training off (songs with loops are sync only)');
    expect(songMissing({ ...ok, rights: completeSong().rights })).toContain('loop 1 creator in the splits');
    expect(songMissing({ ...ok, declarations: { ...loops, loops: [{ ...LOOP, file: null }] } }))
      .toContain('loop 1 license');
    expect(songMissing({ ...ok, declarations: { ...loops, loops: [emptyLoop()] } })).toContain('loop 1 details');
  });

  test('sync needs every writer\'s PRO and IPI', () => {
    const s = completeSong({ consentAi: false, consentSync: true, intake: SYNC_INTAKE, rights: loopRights(false) });
    expect(songMissing(s)).toContain("every writer's PRO and IPI");
  });

  test('sync needs the not-offered-elsewhere box', () => {
    const s = completeSong({ consentAi: false, consentSync: true, intake: { ...SYNC_INTAKE, sync_sole_attested: false } });
    expect(songMissing(s)).toContain('sync details');
  });

  test('declarations payload: loops only for loop songs, detail only for partial', () => {
    expect(buildDeclarationsPayload({ ...ORIGINAL, ai_tools_detail: 'x', loops: [LOOP] }))
      .toEqual({ samples: 'original', samples_attested: true, loops: [], ai_tools: 'none',
        ai_tools_detail: '', ai_tools_attested: true });
    const p = buildDeclarationsPayload({ ...ORIGINAL, samples: 'royalty_free_loop',
      loops: [{ ...LOOP, creator_email: ' Jordan@Example.com ' }] });
    expect(p.loops).toEqual([{ creator_name: 'Jordan Producer', creator_email: 'jordan@example.com',
      source: 'Splice', loop_name: 'Dusty Keys' }]);
  });

  test('runBatch reports failures and carries license warnings', async () => {
    const { states, patchSong } = makeRecorder();
    const songs = [completeSong(), completeSong()];
    const doUpload = jest.fn()
      .mockResolvedValueOnce({ submissionId: 'a', warning: 'A loop license did not upload. Add it from your Vault.' })
      .mockRejectedValueOnce(err(500, 'boom'));
    const res = await runBatch(songs, { getToken: async () => 't', patchSong, doUpload, sleep: async () => {} });
    expect(res).toEqual({ stopReason: null, failed: 1 });
    expect(states[songs[0].key].warning).toMatch(/Vault/);
    expect(states[songs[1].key].status).toBe('failed');
  });
});


describe('Oct 26 changes', () => {
  test('legal name must match the account, ignoring case and spacing', () => {
    const r = (name) => ({ ...completeSong().rights, self_legal_name: name, account_legal_name: 'Jane Q Smith' });
    expect(legalNameMismatch(r('jane  q smith'))).toBe(false);
    expect(legalNameMismatch(r('Stage Name'))).toBe(true);
    expect(songMissing(completeSong({ rights: r('Stage Name') }))).toContain('your legal name as on your account');
    expect(legalNameMismatch({ ...completeSong().rights, account_legal_name: '' })).toBe(false);  // admins
  });

  test('PRO "Other" needs the PRO name, in the sync answers and on writer rows', () => {
    expect(isIntakeValid({ ...SYNC_INTAKE, pro_name: 'Other' })).toBe(false);
    expect(isIntakeValid({ ...SYNC_INTAKE, pro_name: 'Other', pro_other: 'KODA' })).toBe(true);
    expect(buildIntakePayload({ ...SYNC_INTAKE, pro_name: 'Other', pro_other: ' KODA ' }).pro_other).toBe('KODA');
    expect(buildIntakePayload(SYNC_INTAKE).pro_other).toBeNull();
    const r = loopRights();
    r.writers[1] = { ...r.writers[1], society: 'Other', society_other: '' };
    expect(writersMissingPro(r)).toHaveLength(1);
    r.writers[1].society_other = 'KODA';
    expect(writersMissingPro(r)).toHaveLength(0);
  });
});

// Oct 26: "Other" answers need the typed name, and IPI takes 9 to 11 digits.
describe('Other answers and IPI lengths', () => {
  test('genre Other needs which genre', () => {
    const s = completeSong({ form: { artist_name: 'A', track_name: 'T', genre: 'Other', genre_other: ' ' } });
    expect(songMissing(s)).toContain('which genre');
    const ok = completeSong({ form: { artist_name: 'A', track_name: 'T', genre: 'Other', genre_other: 'Drill' } });
    expect(songMissing(ok)).not.toContain('which genre');
  });

  test('distributor Other needs which distributor', () => {
    expect(isIntakeValid({ ...SYNC_INTAKE, distributor: 'Other', distributor_other: '' })).toBe(false);
    const filled = { ...SYNC_INTAKE, distributor: 'Other', distributor_other: ' Ditto Music ' };
    expect(isIntakeValid(filled)).toBe(true);
    expect(buildIntakePayload(filled).distributor_other).toBe('Ditto Music');
    expect(buildIntakePayload({ ...SYNC_INTAKE, distributor_other: 'x' }).distributor_other).toBeNull();
  });

  test.each(['123456789', '1234567890', '00123456789'])('IPI %s is accepted', (ipi) => {
    expect(isIntakeValid({ ...SYNC_INTAKE, ipi })).toBe(true);
  });

  test.each(['12345678', '123456789012'])('IPI %s is refused', (ipi) => {
    expect(isIntakeValid({ ...SYNC_INTAKE, ipi })).toBe(false);
  });
});
