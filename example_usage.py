#!/usr/bin/env python3
"""
Example usage of the audio material management system
"""

import numpy as np
from backend.audio_service import create_audio_service
import sys
import os
import logging

# Add backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))


def main():
    """Main example function"""
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("Starting audio management system example...")

    try:
        # Create audio service (make sure Milvus is running)
        logger.info("Creating audio service...")
        audio_service = create_audio_service(
            milvus_host="localhost",
            milvus_port="19530"
        )

        # Get service info
        logger.info("Getting service info...")
        service_info = audio_service.get_service_info()
        print(f"Service Info: {service_info}")

        # Example 1: Add single audio with description
        logger.info("Adding single audio item...")
        audio_id1 = audio_service.add_audio_with_description(
            path="/data/audio/background_music.mp3",
            description="Peaceful piano music for meditation and relaxation scenes",
            audio_type="music",
            duration=180
        )
        print(f"Added audio item with ID: {audio_id1}")

        # Example 2: Add multiple audio items in batch
        logger.info("Adding batch audio items...")
        batch_data = [
            {
                "path": "/data/audio/narrator_intro.wav",
                "description": "Professional male narrator voice introducing the story",
                "type": "speech",
                "duration": 45
            },
            {
                "path": "/data/audio/door_creak.wav",
                "description": "Old wooden door creaking open slowly",
                "type": "sound_effect",
                "duration": 5
            },
            {
                "path": "/data/audio/ocean_waves.mp3",
                "description": "Gentle ocean waves lapping on shore ambient sound",
                "type": "ambient",
                "duration": 300
            }
        ]

        batch_ids = audio_service.add_audio_batch_with_descriptions(batch_data)
        print(f"Added batch audio items with IDs: {batch_ids}")

        # Example 3: Update audio description
        logger.info("Updating audio description...")
        success = audio_service.update_audio_description(
            audio_id1,
            "Uplifting piano melody perfect for happy ending scenes",
            duration=185  # Also update duration
        )
        print(f"Updated audio description: {success}")

        # Example 4: Update other fields
        logger.info("Updating audio fields...")
        success = audio_service.update_audio(
            batch_ids[0],
            {
                "type": "narration",
                "duration": 50
            }
        )
        print(f"Updated audio fields: {success}")

        # Example 5: Delete single audio
        logger.info("Deleting single audio...")
        success = audio_service.delete_audio(audio_id1)
        print(f"Deleted audio: {success}")

        # Example 6: Delete by type
        logger.info("Deleting audio by type...")
        deleted_count = audio_service.delete_audio_by_type("sound_effect")
        print(f"Deleted {deleted_count} sound_effect items")

        # Example 7: Delete by duration range
        logger.info("Deleting audio by duration range...")
        deleted_count = audio_service.delete_audio_by_duration_range(
            min_duration=200,  # Delete audio longer than 200 seconds
            max_duration=None
        )
        print(f"Deleted {deleted_count} long duration items")

        logger.info("Example completed successfully!")

    except Exception as e:
        logger.error(f"Error in example: {str(e)}")
        raise

    finally:
        # Clean up
        try:
            audio_service.close()
            logger.info("Audio service closed")
        except:
            pass


if __name__ == "__main__":
    main()
