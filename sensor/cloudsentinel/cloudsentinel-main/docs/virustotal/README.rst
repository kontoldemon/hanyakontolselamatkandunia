.. SPDX-FileCopyrightText: 2025 Michel Oosterhof <michel@oosterhof.net>
..
.. SPDX-License-Identifier: BSD-3-Clause

VirusTotal Integration
======================

Overview
--------

The VirusTotal output plugin integrates CloudSentinel honeypot with VirusTotal's v3 API to automatically scan and track malicious files and URLs captured by the honeypot.

Features
--------

* **File Scanning**: Automatically check downloaded files against VirusTotal's database
* **File Uploading**: Upload new malware samples to VirusTotal for analysis
* **URL Scanning**: Check malicious URLs for existing reports
* **URL Submission**: Submit new URLs for scanning
* **Comments**: Add CloudSentinel attribution comments to files and URLs (with #CloudSentinel hashtag)
* **Collections**: Organize all CloudSentinel artifacts in a dedicated VirusTotal collection for easy tracking

Prerequisites
-------------

1. **VirusTotal API Key**: Sign up for a free API key at https://www.virustotal.com/
2. **API Rate Limits**: Be aware of API rate limits (free tier: 4 requests/minute, 500 requests/day)

Configuration
-------------

Add the following to your ``etc/cloudsentinel.cfg`` file:

.. code-block:: ini

    [output_virustotal]
    enabled = true

    # Your VirusTotal API key (required)
    api_key = 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

    # Upload new files to VirusTotal (default: True)
    upload = true

    # Enable debug logging (default: False)
    debug = false

    # Scan downloaded files (default: True)
    scan_file = true

    # Scan URLs (default: True)
    # Note: This doubles API requests for downloads
    scan_url = true

    # Optional: Collection name for organizing artifacts
    # If not set, no collection will be created
    collection = cloudsentinel

    # Optional: Custom comment text (default: CloudSentinel attribution)
    #commenttext = First seen by #CloudSentinel SSH/telnet Honeypot http://github.com/cloudsentinel/cloudsentinel

Configuration Options
---------------------

api_key (required)
~~~~~~~~~~~~~~~~~~

Your VirusTotal API key. Get one at https://www.virustotal.com/gui/my-apikey

upload (optional, default: True)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Whether to upload new files to VirusTotal. If ``false``, only existing reports will be retrieved.

scan_file (optional, default: True)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enable scanning of downloaded files. When enabled:

1. File hash is checked against VirusTotal database
2. If not found and ``upload=true``, file is uploaded for analysis
3. If upload is successful and ``comment=true``, a comment is added
4. If collection is configured, file is added to the collection

scan_url (optional, default: True)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enable scanning of URLs from which files were downloaded. **Note**: This doubles the number of API requests for each file download event.

When enabled:

1. URL is checked against VirusTotal database
2. If not found, URL is submitted for scanning
3. If submission is successful and ``comment=true``, a comment is added
4. If collection is configured, URL is added to the collection

comment (optional, default: True)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add a comment to newly uploaded files and submitted URLs. The comment includes:

* CloudSentinel attribution
* Link to CloudSentinel GitHub repository
* ``#CloudSentinel`` hashtag for easy searching in VirusTotal

collection (optional, default: None)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Name of a VirusTotal collection to organize all CloudSentinel artifacts. When set:

* Collection is automatically created on CloudSentinel startup (if it doesn't exist)
* All uploaded files are added to the collection
* All submitted URLs are added to the collection
* Provides centralized view of all honeypot findings in VirusTotal

**Benefits**:

* Track all artifacts in one place
* Share collection with other researchers
* Monitor honeypot activity over time
* Export IOCs from the collection

If not set or commented out, no collection operations will be performed.

debug (optional, default: False)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enable verbose logging for troubleshooting. Shows:

* Full API request/response details
* Collection operations
* Error details

Output Events
-------------

The plugin logs events with the following event IDs:

cloudsentinel.virustotal.scanfile
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Logged when a file scan result is retrieved.

**Attributes**:

* ``session``: CloudSentinel session ID
* ``sha256``: File SHA-256 hash
* ``positives``: Number of antivirus engines detecting file as malicious
* ``total``: Total number of antivirus engines
* ``scan_date``: Date when file was last scanned
* ``scans``: Dictionary of per-engine scan results
* ``is_new``: ``"true"`` if file was newly uploaded, ``"false"`` if existing

cloudsentinel.virustotal.scanurl
~~~~~~~~~~~~~~~~~~~~~~~~~~

Logged when a URL scan result is retrieved.

**Attributes**:

* ``session``: CloudSentinel session ID
* ``url``: The scanned URL
* ``positives``: Number of engines flagging URL as malicious
* ``total``: Total number of engines
* ``scan_date``: Date when URL was last scanned
* ``scans``: Dictionary of per-engine scan results
* ``is_new``: ``"true"`` if URL was newly submitted, ``"false"`` if existing

Example Output
--------------

File scan result (existing file):

.. code-block:: json

    {
      "eventid": "cloudsentinel.virustotal.scanfile",
      "session": "abc123def456",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "positives": 45,
      "total": 70,
      "scan_date": "2025-10-08T12:34:56Z",
      "is_new": "false",
      "scans": {
        "avast": {"detected": "true", "result": "trojan.generic"},
        "kaspersky": {"detected": "true", "result": "trojan.win32.generic"}
      }
    }

URL scan result (newly submitted):

.. code-block:: json

    {
      "eventid": "cloudsentinel.virustotal.scanurl",
      "session": "abc123def456",
      "url": "http://malicious-site.example.com/payload.exe",
      "positives": 12,
      "total": 68,
      "scan_date": "2025-10-08T12:35:00Z",
      "is_new": "true"
    }

Collections
-----------

Collections organize related files and URLs in VirusTotal for better tracking and analysis.

Setting Up a Collection
~~~~~~~~~~~~~~~~~~~~~~~~

1. Add ``collection = cloudsentinel`` to your configuration
2. Restart CloudSentinel
3. Collection will be automatically created on first startup
4. All subsequent uploads/submissions will be added to this collection

Accessing Your Collection
~~~~~~~~~~~~~~~~~~~~~~~~~~

View your collection in VirusTotal:

``https://www.virustotal.com/gui/collection/<collection-id>``

The collection ID is logged when the collection is created.

Collection Features
~~~~~~~~~~~~~~~~~~~

* **Centralized View**: All honeypot artifacts in one place
* **Search & Filter**: Filter by file type, detection rate, submission date
* **Export**: Export IOCs in various formats (STIX, CSV, etc.)
* **Sharing**: Share collection with other researchers (enterprise feature)
* **Comments**: View all CloudSentinel-attributed comments on items

Best Practices
--------------

Rate Limiting
~~~~~~~~~~~~~

Free VirusTotal API tier has strict rate limits:

* 4 requests per minute
* 500 requests per day

**Recommendations**:

* Set ``scan_url = false`` to reduce API usage (disabling URL scans halves the API requests)
* Monitor your API usage in VirusTotal dashboard
* Consider upgrading to paid tier for high-traffic honeypots

Duplicate Prevention
~~~~~~~~~~~~~~~~~~~~

CloudSentinel automatically prevents duplicate scans using:

* **File deduplication**: Files are only scanned once per download (based on modification time)
* **URL caching**: URLs are cached to prevent repeated lookups within the same session

Collection Management
~~~~~~~~~~~~~~~~~~~~~

* Use descriptive collection names (e.g., ``cloudsentinel-prod``, ``cloudsentinel-lab``)
* Create separate collections for different honeypot deployments
* Regularly review collection contents in VirusTotal

Privacy Considerations
~~~~~~~~~~~~~~~~~~~~~~

**Important**: Files and URLs uploaded to VirusTotal become **publicly accessible** to all VirusTotal users.

* Do not upload sensitive files
* Be aware that malware samples will be shared with security community
* URLs will be visible to other researchers

Troubleshooting
---------------

API Key Errors
~~~~~~~~~~~~~~

.. code-block:: text

    VT scanfile failed: 401 Unauthorized

**Solution**: Verify your API key is correct in ``cloudsentinel.cfg``

Rate Limit Errors
~~~~~~~~~~~~~~~~~

.. code-block:: text

    VT: Error - QuotaExceededError: Quota exceeded

**Solutions**:

* Wait for rate limit to reset (1 minute for request limit, 24 hours for daily limit)
* Reduce scan frequency by disabling ``scan_url``
* Upgrade to paid API tier

Collection Already Exists
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    VT: Collection 'cloudsentinel' already exists - will use existing

**Not an error**: This is normal behavior. The plugin will reuse the existing collection.

Debug Mode
~~~~~~~~~~

Enable debug mode to see detailed API interactions:

.. code-block:: ini

    [output_virustotal]
    debug = true

This will log full request/response details to help diagnose issues.

API Reference
-------------

The plugin uses VirusTotal v3 API endpoints:

* ``GET /api/v3/files/{hash}`` - Retrieve file scan report
* ``POST /api/v3/files`` - Upload new file
* ``POST /api/v3/files/{id}/comments`` - Add comment to file
* ``GET /api/v3/urls/{url_id}`` - Retrieve URL scan report
* ``POST /api/v3/urls`` - Submit URL for scanning
* ``POST /api/v3/urls/{id}/comments`` - Add comment to URL
* ``POST /api/v3/collections`` - Create collection
* ``POST /api/v3/collections/{id}/files`` - Add file to collection
* ``POST /api/v3/collections/{id}/urls`` - Add URL to collection

For complete API documentation, see: https://docs.virustotal.com/reference/overview

Contributing
------------

To contribute improvements to the VirusTotal integration:

1. Fork the CloudSentinel repository
2. Create a feature branch
3. Make your changes to ``src/cloudsentinel/output/virustotal.py``
4. Add tests to ``src/cloudsentinel/test/test_virustotal.py``
5. Run the test suite: ``python -m pytest src/cloudsentinel/test/test_virustotal.py -v``
6. Run type checking: ``mypy src/cloudsentinel/output/virustotal.py``
7. Run linting: ``ruff check src/cloudsentinel/output/virustotal.py``
8. Submit a pull request

License
-------

The VirusTotal integration is part of CloudSentinel and is licensed under the same BSD license.

Support
-------

* **Documentation**: https://cloudsentinel.readthedocs.io/
* **Issues**: https://github.com/cloudsentinel/cloudsentinel/issues
* **Discussions**: https://github.com/cloudsentinel/cloudsentinel/discussions
* **VirusTotal Support**: https://support.virustotal.com/
