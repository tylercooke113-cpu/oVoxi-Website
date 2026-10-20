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

// A song that passes every validation rule (owns everything, AI consent only).
const completeSong = (over = {}) => emptySong({
  form: { artist_name: 'Artist', track_name: 'Track', genre: 'Pop' },
  file: { name: 'track.wav', size: 1000 },
  moods: ['Chill'],
  vocals: 'vocal',
  bpm: '120',
  musicalKey: 'C major',
  consentAi: true,
  rights: { ...emptyRights(), owns_everything: true, self_legal_name: 'Real Name', attested: true },
  ...over,
});

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
      intake: {
        samples: 'none',
        samples_attested: true,
        distributor: 'DistroKid',
        content_id: 'no',
        pro_not_affiliated: false,
        pro_name: 'ASCAP',
        ipi: '123456789',
      },
      rights: { ...emptyRights(), self_legal_name: 'Legal Name', legal_name_touched: true },
    });

    const next = carryOverSong(prev);

    // Carried over
    expect(next.form.artist_name).toBe('Carry Me');
    expect(next.consentAi).toBe(true);
    expect(next.consentSync).toBe(true);
    expect(next.intake.distributor).toBe('DistroKid');
    expect(next.intake.pro_not_affiliated).toBe(false);
    expect(next.intake.pro_name).toBe('ASCAP');
    expect(next.intake.ipi).toBe('123456789');
    expect(next.rights.self_legal_name).toBe('Legal Name');
    expect(next.rights.legal_name_touched).toBe(true);

    // Reset
    expect(next.form.track_name).toBe('');
    expect(next.form.genre).toBe('');
    expect(next.file).toBeNull();
    expect(next.intake.samples).toBe('');
    expect(next.intake.samples_attested).toBe(false);
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
