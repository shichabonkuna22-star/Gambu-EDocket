// ============================================================
// OFFLINE SYNC ENGINE FOR SAPS eDocket
// Uses Dexie.js for IndexedDB
// ============================================================

// ------------------------------------------------------------------
// 1. Database Setup
// ------------------------------------------------------------------
const db = new Dexie('SAPS_Offline');
db.version(1).stores({
    cases: '++id, case_number, synced, created_at, local_id',
    suspects: '++id, id_number, synced, local_id',
    evidence: '++id, case_id, file_data, file_name, file_type, synced',
    sync_queue: '++id, endpoint, method, payload, attempts, timestamp'
});

// ------------------------------------------------------------------
// 2. Sync Status UI
// ------------------------------------------------------------------
const syncIcon = document.getElementById('syncIcon');
const syncText = document.getElementById('syncText');

function updateSyncStatus(online) {
    if (online) {
        syncIcon.className = 'fas fa-wifi text-success';
        syncText.textContent = 'Online';
    } else {
        syncIcon.className = 'fas fa-wifi text-danger';
        syncText.textContent = 'Offline';
    }
}

// Detect online/offline
window.addEventListener('online', () => {
    updateSyncStatus(true);
    syncNow(); // trigger sync when back online
});
window.addEventListener('offline', () => updateSyncStatus(false));

// Initial status
updateSyncStatus(navigator.onLine);

// ------------------------------------------------------------------
// 3. Helper: Save a case offline
// ------------------------------------------------------------------
export async function saveCaseOffline(caseData, files = {}) {
    // Generate a temporary local ID
    const localId = Date.now() + '_' + Math.random().toString(36).substr(2, 6);
    caseData.local_id = localId;
    caseData.synced = false;
    caseData.created_at = new Date().toISOString();

    // Save suspect separately if new
    const suspectData = {
        id_number: caseData.id_number,
        first_name: caseData.first_name,
        last_name: caseData.last_name,
        date_of_birth: caseData.date_of_birth,
        gender: caseData.gender,
        address: caseData.address,
        contact_number: caseData.contact_number,
        local_id: localId,
        synced: false
    };
    await db.suspects.add(suspectData);

    // Save the case
    const caseId = await db.cases.add({
        ...caseData,
        local_id: localId,
        suspect_local_id: localId
    });

    // Save evidence files (blobs) if any
    if (files.photo) {
        await db.evidence.add({
            case_id: caseId,
            file_data: files.photo,
            file_name: files.photo.name,
            file_type: 'photo',
            synced: false,
            local_id: localId
        });
    }
    if (files.fingerprint) {
        await db.evidence.add({
            case_id: caseId,
            file_data: files.fingerprint,
            file_name: files.fingerprint.name,
            file_type: 'fingerprint',
            synced: false,
            local_id: localId
        });
    }
    if (files.evidence && files.evidence.length) {
        for (const file of files.evidence) {
            await db.evidence.add({
                case_id: caseId,
                file_data: file,
                file_name: file.name,
                file_type: 'evidence',
                synced: false,
                local_id: localId
            });
        }
    }

    // Queue the case creation for sync
    await db.sync_queue.add({
        endpoint: '/api/cases',
        method: 'POST',
        payload: caseData,
        attempts: 0,
        timestamp: Date.now()
    });

    // Also queue file uploads separately
    // We'll handle file uploads during sync

    return caseId;
}

// ------------------------------------------------------------------
// 4. Sync Engine
// ------------------------------------------------------------------
export async function syncNow() {
    if (!navigator.onLine) {
        console.log('Offline – sync postponed');
        return;
    }

    console.log('Starting sync...');
    const queue = await db.sync_queue.toArray();
    if (queue.length === 0) {
        console.log('No pending sync items');
        return;
    }

    // Process each item
    for (const item of queue) {
        try {
            const response = await fetch(item.endpoint, {
                method: item.method || 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(item.payload)
            });

            if (response.ok) {
                const result = await response.json();
                // If case creation succeeded, update local case with real case_number and mark synced
                if (item.endpoint === '/api/cases' && result.success) {
                    const localId = item.payload.local_id;
                    await db.cases.where('local_id').equals(localId).modify({
                        case_number: result.case_number,
                        synced: true,
                        server_id: result.case_id
                    });
                    await db.suspects.where('local_id').equals(localId).modify({
                        synced: true,
                        server_id: result.suspect_id
                    });
                    // Now upload evidence files for this case
                    await uploadEvidenceForCase(localId, result.case_id);
                }
                // Remove from queue
                await db.sync_queue.delete(item.id);
            } else {
                // If failed, increment attempts (will retry later)
                await db.sync_queue.update(item.id, { attempts: item.attempts + 1 });
                console.warn('Sync item failed, retry later:', item);
            }
        } catch (error) {
            console.error('Sync error:', error);
            // Network error, will retry later
        }
    }
}

// ------------------------------------------------------------------
// 5. Upload Evidence Files
// ------------------------------------------------------------------
async function uploadEvidenceForCase(localId, caseId) {
    const evidenceItems = await db.evidence.where('local_id').equals(localId).toArray();
    for (const ev of evidenceItems) {
        if (ev.synced) continue;
        const formData = new FormData();
        formData.append('file', ev.file_data);
        formData.append('type', ev.file_type);
        formData.append('case_id', caseId);
        if (ev.file_type === 'photo' || ev.file_type === 'fingerprint') {
            // For suspect photos/fingerprints, we need suspect_id
            const suspect = await db.suspects.where('local_id').equals(localId).first();
            if (suspect && suspect.server_id) {
                formData.append('suspect_id', suspect.server_id);
            }
        }
        try {
            const resp = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            if (resp.ok) {
                await db.evidence.update(ev.id, { synced: true });
            } else {
                console.warn('Evidence upload failed for', ev.file_name);
            }
        } catch (e) {
            console.error('Upload error:', e);
        }
    }
}

// ------------------------------------------------------------------
// 6. Periodic Sync (every 5 minutes if online)
// ------------------------------------------------------------------
setInterval(() => {
    if (navigator.onLine) syncNow();
}, 5 * 60 * 1000);

// Also sync on page load if online
document.addEventListener('DOMContentLoaded', () => {
    if (navigator.onLine) syncNow();
});

// ------------------------------------------------------------------
// 7. Expose functions globally for use in templates
// ------------------------------------------------------------------
window.saveCaseOffline = saveCaseOffline;
window.syncNow = syncNow;