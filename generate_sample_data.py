"""
Generate synthetic Google Takeout watch-history.json data for testing and demo.
Simulates realistic listening patterns:
- Multi-artist tracks, "- Topic" suffixes, "Watched " prefixes
- YouTube Music and regular YouTube entries
- Google Ads entries
- Deleted/missing subtitles / URL-only titles
- Realistic timestamp gaps (consecutive plays, skips <30s, long pauses between sessions)
- Loops and obsessions across years (e.g. 2022-2025)
"""
import json
import random
from datetime import datetime, timedelta, timezone

def generate_sample_watch_history(
    num_entries: int = 1500,
    output_path: str = "sample_watch_history.json",
    seed: int = 42
) -> str:
    random.seed(seed)

    artists = [
        "Daft Punk", "The Weeknd", "Taylor Swift", "Radiohead", "Billie Eilish",
        "Kendrick Lamar", "Pink Floyd", "Dua Lipa", "Coldplay", "Arctic Monkeys",
        "Hans Zimmer", "Arijit Singh", "Pritam", "Diljit Dosanjh", "AR Rahman"
    ]
    
    songs = {
        "Daft Punk": ["Get Lucky", "One More Time", "Instant Crush", "Harder, Better, Faster, Stronger", "Around the World"],
        "The Weeknd": ["Blinding Lights", "Starboy", "Save Your Tears", "Die For You", "The Hills"],
        "Taylor Swift": ["Cruel Summer", "Blank Space", "Anti-Hero", "Style", "Cardigan"],
        "Radiohead": ["Creep", "Karma Police", "No Surprises", "Paranoid Android", "Weird Fishes"],
        "Billie Eilish": ["bad guy", "birds of a feather", "ocean eyes", "everything i wanted", "happier than ever"],
        "Kendrick Lamar": ["HUMBLE.", "DNA.", "Not Like Us", "Alright", "Money Trees"],
        "Pink Floyd": ["Comfortably Numb", "Wish You Were Here", "Time", "Money", "Shine On You Crazy Diamond"],
        "Dua Lipa": ["Levitating", "Don't Start Now", "Physical", "Dance The Night", "New Rules"],
        "Coldplay": ["Yellow", "Viva La Vida", "The Scientist", "Fix You", "Clocks"],
        "Arctic Monkeys": ["Do I Wanna Know?", "505", "R U Mine?", "Why'd You Only Call Me When You're High?", "Fluorescent Adolescent"],
        "Hans Zimmer": ["Time (Inception)", "Cornfield Chase (Interstellar)", "Now We Are Free", "Stay", "Mountains"],
        "Arijit Singh": ["Tum Hi Ho", "Channa Mereya", "Kesariya", "Agar Tum Saath Ho", "Kalank"],
        "Pritam": ["Subhanallah", "Kabira", "Shayad", "Bulleya", "Raabta"],
        "Diljit Dosanjh": ["Lover", "Born to Shine", "Proper Patola", "GOAT", "Kinni Kinni"],
        "AR Rahman": ["Kun Faya Kun", "Jai Ho", "Dil Se Re", "Tere Bina", "Khwaja Mere Khwaja"]
    }

    # Generate video IDs per track for consistency
    track_ids = {}
    for artist, track_list in songs.items():
        for track in track_list:
            fake_id = "".join(random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_", k=11))
            track_ids[(artist, track)] = fake_id

    # Start date ~ 2 years ago
    current_time = datetime(2023, 1, 1, 8, 30, 0, tzinfo=timezone.utc)
    entries = []

    # Create entries forward in time
    for i in range(num_entries):
        # 3% chance of Google Ad
        if random.random() < 0.03:
            entries.append({
                "header": "YouTube",
                "title": "Watched Some Sponsored Commercial Ad",
                "titleUrl": "https://www.youtube.com/watch?v=ad123456789",
                "subtitles": [{"name": "Ad Company", "url": "https://www.youtube.com/channel/ad"}],
                "time": current_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z",
                "products": ["YouTube"],
                "details": [{"name": "From Google Ads"}],
                "activityControls": ["YouTube watch history"]
            })
            current_time += timedelta(seconds=random.randint(15, 60))
            continue

        # 4% chance of regular YouTube video (not music)
        if random.random() < 0.04:
            entries.append({
                "header": "YouTube",
                "title": f"Watched Tech Review Episode #{random.randint(1, 100)}",
                "titleUrl": "https://www.youtube.com/watch?v=yt_tech_video",
                "subtitles": [{"name": "Tech Channel", "url": "https://www.youtube.com/channel/tech"}],
                "time": current_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z",
                "products": ["YouTube"],
                "activityControls": ["YouTube watch history"]
            })
            current_time += timedelta(minutes=random.randint(5, 20))
            continue

        # 2% chance of removed / deleted video (missing subtitles / URL-only title)
        if random.random() < 0.02:
            entries.append({
                "header": "YouTube Music",
                "title": "https://music.youtube.com/watch?v=deletedvid01",
                "titleUrl": "https://music.youtube.com/watch?v=deletedvid01",
                "time": current_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z",
                "products": ["YouTube"],
                "activityControls": ["YouTube watch history"]
            })
            current_time += timedelta(seconds=random.randint(10, 200))
            continue

        # 2% chance of missing subtitle but with title
        if random.random() < 0.02:
            entries.append({
                "header": "YouTube Music",
                "title": "Watched Private Track Upload",
                "titleUrl": "https://music.youtube.com/watch?v=privatevid02",
                "time": current_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z",
                "products": ["YouTube"],
                "activityControls": ["YouTube watch history"]
            })
            current_time += timedelta(seconds=random.randint(180, 240))
            continue

        # Pick artist and track (weighted towards favorites for realistic Zipf distribution)
        artist_weights = [15, 12, 10, 8, 8, 7, 6, 6, 5, 5, 4, 4, 4, 3, 3]
        artist = random.choices(artists, weights=artist_weights, k=1)[0]
        track = random.choice(songs[artist])
        vid_id = track_ids[(artist, track)]

        # Suffix variation: "- Topic" in subtitles
        sub_name = f"{artist} - Topic" if random.random() < 0.85 else artist
        # Feature variation
        if random.random() < 0.15:
            collab_artist = random.choice([a for a in artists if a != artist])
            track_title = f"{track} (feat. {collab_artist})"
        else:
            track_title = track

        entry = {
            "header": "YouTube Music",
            "title": f"Watched {track_title}",
            "titleUrl": f"https://music.youtube.com/watch?v={vid_id}",
            "subtitles": [{"name": sub_name, "url": f"https://music.youtube.com/channel/{artist.replace(' ', '')}"}],
            "time": current_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z",
            "products": ["YouTube"],
            "activityControls": ["YouTube watch history"]
        }
        entries.append(entry)

        # 5% chance of instant duplicate (same timestamp / replay glitch)
        if random.random() < 0.03:
            entries.append(dict(entry))

        # Time advancement:
        # 10% chance of a skip (<30s)
        # 10% chance of loop (same song again immediately)
        # 60% standard song play (2.5 - 5 min)
        # 17% session break (35 min - 12 hours)
        # 3% multiday break (1 - 5 days)
        rand_action = random.random()
        if rand_action < 0.10:
            current_time += timedelta(seconds=random.randint(5, 28))
        elif rand_action < 0.20:
            # Loop next!
            current_time += timedelta(seconds=random.randint(180, 240))
            entries.append({
                "header": "YouTube Music",
                "title": f"Watched {track_title}",
                "titleUrl": f"https://music.youtube.com/watch?v={vid_id}",
                "subtitles": [{"name": sub_name, "url": f"https://music.youtube.com/channel/{artist.replace(' ', '')}"}],
                "time": current_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z",
                "products": ["YouTube"],
                "activityControls": ["YouTube watch history"]
            })
            current_time += timedelta(seconds=random.randint(180, 240))
        elif rand_action < 0.80:
            current_time += timedelta(seconds=random.randint(150, 310))
        elif rand_action < 0.97:
            current_time += timedelta(minutes=random.randint(35, 720))
        else:
            current_time += timedelta(days=random.randint(1, 5), hours=random.randint(1, 8))

    # Google Takeout watch-history.json is reverse chronological (newest first)
    entries.reverse()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(entries)} synthetic entries to {output_path}")
    return output_path

if __name__ == "__main__":
    generate_sample_watch_history(1500, "sample_watch_history.json")
