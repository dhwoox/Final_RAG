This guide teaches you how to generate, validate, and manage test data for G-SDK Python automation tests. Use this guide to understand data generation patterns rather than case-specific examples.

---

## Section 1: User Data Generation

### 1.1 User ID Generation

**Category**: `user`

**Decision Tree for User ID Type**:

```
Is device alphanumeric ID capable?
├─ YES → Use randomAlphanumericUserID() or generateName()
└─ NO  → Use randomNumericUserID()
```

**Random Numeric User ID**:

```python
from util import randomNumericUserID

userID = randomNumericUserID()  # Returns string "1" to "4294967294"
```

**Random Alphanumeric User ID**:

```python
from util import randomAlphanumericUserID

# Auto length (1-32 chars)
userID = randomAlphanumericUserID()

# Fixed length
userID = randomAlphanumericUserID(lenOfUserID=16)

# With additional characters
userID = randomAlphanumericUserID(expending=['@', '.'])
```

**Characters allowed**: `a-z`, `A-Z`, `0-9`, `_`, `-`, plus any in `expending` list

**Name-based User ID**:

```python
from util import generateName
import device_pb2

# For station devices with Korean support
name = generateName(
    includeKorean=True,
    includeEnglish=True,
    includeNumber=True,
    includeSpecialChar=True,
    length=24,
    maxLength=48
)

# For specific device type
name = generateRandomName(
    deviceType=device_pb2.BIOSTATION_3,
    includeKorean=True,
    lengthOfName=32
)
```

### 1.2 PIN Generation

**Category**: `user`, `auth`

**Pattern**:

```python
from util import generateRandomPIN

# Auto length (4-16 digits)
pin = generateRandomPIN()

# Fixed length
pin = generateRandomPIN(lengthOfPin=8)

# Custom range
pin = generateRandomPIN(minLenOfPin=6, maxLenOfPin=10)
```

**Returns**: `bytes` object (e.g., `b'12345678'`)

**Hashing PIN for enrollment**:

```python
# If using manager
hashedPIN = self.svcManager.hashPIN(pin)

# Direct from service
from example.user.user import UserSvc
hashedPIN = userSvc.hashPIN(pin)
```

### 1.3 Card Data Generation

**Category**: `card`, `user`

**Pattern**:

```python
from util import generateCardID, getCardID

# Generate card with random serial
cardData = generateCardID()  # Default 32 bytes

# Generate with specific serial number
cardData = generateCardID(serial_number=123456, length=32)

# Extract serial from card data
serialNumber = getCardID(cardData, reverse=False)
```

**Card Input Helper**:

```python
from cli.input import makeupCardData

# Convert string/int to proper card data format
cardData = makeupCardData("123456")
```

### 1.4 Biometric Data (Fingerprint/Face)

**Category**: `finger`, `face`, `user`

**Fingerprint Data**:

- **Source**: Must scan from actual device or use pre-captured templates
- **Reference files**:
  - `demo/example/finger/test/fingerDB/` - Pre-scanned templates
  - `manager.py` - `scanFingerprint()`, `extractFingerTemplates()`

**Pattern**:

```python
# Scan fingerprint from device
fingerData = self.svcManager.scanFingerprint(deviceID)

# Use pre-captured template
import os
templatePath = self.getDataFilePath('finger_template.bin', 'fingerDB')
with open(templatePath, 'rb') as f:
    fingerData = f.read()

# Create UserFinger object
import user_pb2
userFinger = user_pb2.FingerData(
    index=0,  # First finger
    flag=0,
    templates=[fingerData]
)
```

**Face Data**:

- **Source**: Must extract from device or use pre-captured face templates
- **Reference files**:
  - `demo/example/face/` - Face extraction examples
  - `manager.py` - `extractFaceTemplates()`

**Pattern**:

```python
# Extract face from device
faceData = self.svcManager.extractFaceTemplates(deviceID, userID)

# Create UserFace object
import user_pb2
userFace = user_pb2.FaceData(
    index=0,
    flag=0,
    templates=[faceData]
)
```

### 1.5 User Photo

**Category**: `user`

**Pattern**:

```python
from PIL import Image
import io

# Load image from file
imagePath = self.getDataFilePath('user_photo.jpg', 'images')
with open(imagePath, 'rb') as f:
    photoData = f.read()

# Or generate from URL
import requests
response = requests.get('https://example.com/photo.jpg')
photoData = response.content

# Convert to proper format
image = Image.open(io.BytesIO(photoData))
# Resize if needed for device
image = image.resize((240, 320))
buffer = io.BytesIO()
image.save(buffer, format='JPEG')
photoData = buffer.getvalue()
```

### 1.6 Complete User Object

**Pattern**:

```python
import user_pb2

def generateRandomUser(deviceCapability, includeCard=True, includeFinger=False, includeFace=False):
    userID = randomNumericUserID()

    user = user_pb2.UserInfo()
    user.hdr.ID = userID

    # Name
    user.name = generateName(includeKorean=True, length=24)

    # PIN (if supported)
    if deviceCapability.PINSupported:
        pin = generateRandomPIN(lengthOfPin=8)
        user.PIN = self.svcManager.hashPIN(pin)

    # Cards
    if includeCard and deviceCapability.maxCards > 0:
        cardData = generateCardID()
        card = user_pb2.CardData(
            index=0,
            data=cardData
        )
        user.cards.append(card)

    # Fingerprints
    if includeFinger and deviceCapability.maxFingerprints > 0:
        fingerData = self.svcManager.scanFingerprint(self.targetID)
        finger = user_pb2.FingerData(
            index=0,
            templates=[fingerData]
        )
        user.fingers.append(finger)

    # Faces
    if includeFace and deviceCapability.maxFaces > 0:
        faceData = self.svcManager.extractFaceTemplates(self.targetID, userID)
        face = user_pb2.FaceData(
            index=0,
            templates=[faceData]
        )
        user.faces.append(face)

    return user
```

---

## Section 2: Configuration Data Generation

### 2.1 AuthConfig Data

**Category**: `auth`

**Reference files**:

- `manager.py` - `getAuthConfig()`, `setAuthConfig()`
- `testCOMMONR.py` - `setCardOnlyAuthMode()`, `setFingerprintOnlyAuthMode()`, `setFaceOnlyAuthMode()`, `setAuthmodeEnabled()`
- `auth_pb2.py` - AuthConfig, AuthSchedule structures

**Pattern for Setting Auth Mode**:

```python
# Use helper from testCOMMONR
backup = self.setCardOnlyAuthMode(deviceID, capability, scheduleID=1)

# Or set multiple modes
backup = self.setAuthmodeEnabled(
    deviceID,
    capability,
    cardEnabled=True,
    idEnabled=True,
    fingerEnabled=True,
    faceEnabled=True,
    scheduleID=1
)
```

**Manual AuthConfig Creation**:

```python
import auth_pb2
import copy

# Get current config
authConfig = self.svcManager.getAuthConfig(deviceID)
backup = copy.deepcopy(authConfig)

# Clear existing schedules
del authConfig.authSchedules[:]

# Add new schedule
if capability.extendedCardOnlySupported:
    authSchedule = auth_pb2.AuthSchedule(
        mode=auth_pb2.AUTH_EXT_MODE_CARD_ONLY,
        scheduleID=1  # 1 = always
    )
else:
    authSchedule = auth_pb2.AuthSchedule(
        mode=auth_pb2.AUTH_MODE_CARD_ONLY,
        scheduleID=1
    )

authConfig.authSchedules.append(authSchedule)

# Apply
self.svcManager.setAuthConfig(deviceID, authConfig)
```

**Available Auth Modes**:

- Basic: `AUTH_MODE_CARD_ONLY`, `AUTH_MODE_BIOMETRIC_ONLY`, `AUTH_MODE_ID_PIN`, `AUTH_MODE_CARD_BIOMETRIC`, `AUTH_MODE_CARD_PIN`, `AUTH_MODE_CARD_BIOMETRIC_OR_PIN`, `AUTH_MODE_CARD_BIOMETRIC_PIN`
- Extended: `AUTH_EXT_MODE_CARD_ONLY`, `AUTH_EXT_MODE_FINGERPRINT_ONLY`, `AUTH_EXT_MODE_FACE_ONLY`, `AUTH_EXT_MODE_ID_PIN`, etc.

### 2.2 Fingerprint Sensitivity Config

**Category**: `finger`, `config`

**Reference files**:

- `manager.py` - `getFingerConfig()`, `setFingerConfig()`
- Protocol: `finger.proto`

**Pattern**:

```python
import finger_pb2

# Get current config
fingerConfig = self.svcManager.getFingerConfig(deviceID)

# Modify sensitivity
fingerConfig.securityLevel = finger_pb2.FINGER_SECURITY_NORMAL  # Or STRICT, MOST_STRICT

# Apply
self.svcManager.setFingerConfig(deviceID, fingerConfig)
```

### 2.3 Door Configuration

**Category**: `door`, `access`

**Reference files**:

- `manager.py` - `getDoors()`, `setDoor()`, `removeDoors()`
- `testCOMMONR.py` - Backup/restore pattern in setUp/tearDown
- Protocol: `door.proto`

**Pattern**:

```python
import door_pb2

door = door_pb2.DoorInfo()
door.doorID = 1
door.name = "Main Entrance"
door.entryDeviceID = deviceID
door.exitDeviceID = 0  # No exit device

# Relay settings
door.relay.deviceID = deviceID
door.relay.port = 0

# Sensor settings
door.sensor.deviceID = deviceID
door.sensor.port = 0
door.sensor.type = door_pb2.NORMALLY_CLOSED

# Auto lock settings
door.autoLockTimeout = 3  # seconds
door.heldOpenTimeout = 10  # seconds

# Apply
self.svcManager.setDoor(deviceID, door)
```

### 2.4 Access Group Configuration

**Category**: `access`

**Reference files**:

- `manager.py` - `getAccessGroups()`, `setAccessGroup()`, `removeAccessGroups()`
- Protocol: `access.proto`

**Pattern**:

```python
import access_pb2

accessGroup = access_pb2.AccessGroup()
accessGroup.ID = 1
accessGroup.name = "Employee Group"

# Add access levels
accessGroup.levelIDs.append(1)  # Access level ID

# Apply
self.svcManager.setAccessGroup(deviceID, accessGroup)
```

### 2.5 Access Level Configuration

**Category**: `access`

**Reference files**:

- `manager.py` - `getAccessLevels()`, `setAccessLevel()`, `removeAccessLevels()`
- Protocol: `access.proto`

**Pattern**:

```python
import access_pb2

accessLevel = access_pb2.AccessLevel()
accessLevel.ID = 1
accessLevel.name = "Business Hours Access"

# Add door schedules
doorSchedule = access_pb2.DoorSchedule()
doorSchedule.doorID = 1
doorSchedule.scheduleID = 1  # Always

accessLevel.doorSchedules.append(doorSchedule)

# Apply
self.svcManager.setAccessLevel(deviceID, accessLevel)
```

### 2.6 Schedule Configuration

**Category**: `schedule`, `access`

**Reference files**:

- `util.py` - `onSchedule()`, `onHoliday()`, `onHolidayGroup()`
- Protocol: `schedule.proto`

**Weekly Schedule Pattern**:

```python
import schedule_pb2

schedule = schedule_pb2.Schedule()
schedule.ID = 2
schedule.name = "Business Hours"
schedule.weekly.CopyFrom(schedule_pb2.WeeklySchedule())

# Monday to Friday: 9:00 - 18:00
for day in range(1, 6):  # Monday=1, Friday=5
    daySchedule = schedule_pb2.DaySchedule()
    period = schedule_pb2.TimePeriod()
    period.startTime = 9 * 60  # 9:00 in minutes
    period.endTime = 18 * 60   # 18:00 in minutes
    daySchedule.periods.append(period)
    schedule.weekly.daySchedules.append(daySchedule)

# Apply
self.svcManager.setSchedule(deviceID, schedule)
```

**Daily Schedule Pattern**:

```python
import schedule_pb2
import time

schedule = schedule_pb2.Schedule()
schedule.ID = 3
schedule.name = "Rotating Schedule"
schedule.daily.CopyFrom(schedule_pb2.DailySchedule())
schedule.daily.startDate = int(time.time())

# 3-day rotation
for i in range(3):
    daySchedule = schedule_pb2.DaySchedule()
    period = schedule_pb2.TimePeriod()
    period.startTime = (8 + i) * 60  # Rotating start time
    period.endTime = (17 + i) * 60
    daySchedule.periods.append(period)
    schedule.daily.daySchedules.append(daySchedule)
```

### 2.7 Holiday Configuration

**Category**: `schedule`, `access`

**Pattern**:

```python
import schedule_pb2
import datetime
import time

# Create holiday
holiday = schedule_pb2.Holiday()
holiday.date = int(time.mktime(datetime.datetime(2025, 1, 1).timetuple()))
holiday.recurrence = schedule_pb2.RECUR_YEARLY  # Or RECUR_MONTHLY, RECUR_NONE

# Create holiday group
holidayGroup = schedule_pb2.HolidayGroup()
holidayGroup.ID = 1
holidayGroup.name = "National Holidays"
holidayGroup.holidays.append(holiday)

# Apply
self.svcManager.setHolidayGroup(deviceID, holidayGroup)
```

---

## Section 3: Data Verification Patterns

### 3.1 User Enrollment Verification

**Pattern**:

```python
# Enroll user
users = [generateRandomUser(self.capability)]
self.svcManager.enrollUsers(self.targetID, users)

# Verify enrollment
enrolledUsers = self.svcManager.getUsers(self.targetID)
self.assertEqual(len(enrolledUsers), 1)
self.assertEqual(enrolledUsers[0], users[0])
```

### 3.2 User Statistics Verification

**Pattern**:

```python
# Get statistics after operations
stats = self.svcManager.getUserStatistic(self.targetID)

# Verify counts
self.assertEqual(stats.numOfUsers, expectedUserCount)
self.assertEqual(stats.numOfCards, expectedCardCount)
self.assertEqual(stats.numOfFingers, expectedFingerCount)
self.assertEqual(stats.numOfFaces, expectedFaceCount)
```

### 3.3 Config Setting Verification

**Pattern**:

```python
# Set config
newConfig = createTestConfig()
self.svcManager.setAuthConfig(self.targetID, newConfig)

# Verify
actualConfig = self.svcManager.getAuthConfig(self.targetID)
self.assertEqual(actualConfig, newConfig)
```

### 3.4 Event Verification

**Category**: `event`

**Reference files**:

- `util.py` - `EventMonitor` class
- `manager.py` - `monitorLog()`, `subscribeLog()`, `getEventDescription()`

**Pattern with EventMonitor**:

```python
from util import EventMonitor

# Start monitoring specific event
with EventMonitor(
    self.svcManager,
    self.targetID,
    eventCode=0x1000,  # Specific event code
    userID=testUserID,
    quiet=True  # Only show matching events
) as monitor:

    # Perform action that should trigger event
    performTestAction()

    # Verify event occurred
    self.assertTrue(monitor.caught(timeout=5.0))
    self.assertEqual(monitor.description.userID, testUserID)
```

**Manual Event Verification**:

```python
# Enable monitoring
self.svcManager.monitorLog(self.targetID, True)

# Get recent events
events = self.svcManager.getLog(self.targetID, startEventID=0, maxNumOfLog=100)

# Verify specific event
foundEvent = False
for event in events:
    if event.eventCode | event.subCode == expectedEventCode:
        if event.userID == expectedUserID:
            foundEvent = True
            break

self.assertTrue(foundEvent)
```

---

## Section 4: Data Cleanup Patterns

### 4.1 Automatic Cleanup (Recommended)

**Pattern in testCOMMONR.py**:

```python
def setUp(self):
    # Backup existing data
    self.backupUsers = self.svcManager.getUsers(self.targetID)
    if len(self.backupUsers) == 0:
        self.backupUsers = None

    # Clean for test
    self.svcManager.removeUsers(self.targetID)

def tearDown(self):
    # Remove test data
    self.svcManager.removeUsers(self.targetID)

    # Restore backup
    if self.backupUsers is not None:
        self.svcManager.enrollUsers(self.targetID, self.backupUsers)
```

### 4.2 Manual Cleanup

**Pattern**:

```python
# Remove specific users
userIDsToRemove = ["user1", "user2", "user3"]
self.svcManager.removeUsers(self.targetID, userIDsToRemove)

# Remove all users
self.svcManager.removeUsers(self.targetID)

# Remove specific doors
doorIDsToRemove = [1, 2, 3]
self.svcManager.removeDoors(self.targetID, doorIDsToRemove)

# Remove all access groups
self.svcManager.removeAccessGroups(self.targetID)
```

### 4.3 Config Restore Pattern

**Pattern**:

```python
def setUp(self):
    self.backupAuthMode = self.svcManager.getAuthConfig(self.targetID)
    # ... modify config for test

def tearDown(self):
    self.svcManager.setAuthConfig(self.targetID, self.backupAuthMode)
```

### 4.4 Multi-Resource Cleanup

**Pattern from testCOMMONR.py**:

```python
def setUp(self):
    # Backup all access control resources
    self.backupDoors = self.svcManager.getDoors(self.targetID)
    self.backupAccessLevels = self.svcManager.getAccessLevels(self.targetID)
    self.backupAccessGroups = self.svcManager.getAccessGroups(self.targetID)

    # Clean all
    self.svcManager.removeDoors(self.targetID)
    self.svcManager.removeAccessLevels(self.targetID)
    self.svcManager.removeAccessGroups(self.targetID)

def tearDown(self):
    # Remove test data
    self.svcManager.removeDoors(self.targetID)
    self.svcManager.removeAccessLevels(self.targetID)
    self.svcManager.removeAccessGroups(self.targetID)

    # Restore in order (dependencies matter)
    for door in self.backupDoors:
        self.svcManager.setDoor(self.targetID, door)
    for accessLevel in self.backupAccessLevels:
        self.svcManager.setAccessLevel(self.targetID, accessLevel)
    for accessGroup in self.backupAccessGroups:
        self.svcManager.setAccessGroup(self.targetID, accessGroup)
```

---

## Section 5: Random Data Generation Best Practices

### 5.1 Device Capability Check

**Always check capability before generating data**:

```python
def generateUserForDevice(deviceID, svcManager):
    capability = svcManager.getDeviceCapability(deviceID)
    capInfo = svcManager.getCapabilityInfo(deviceID)

    user = user_pb2.UserInfo()

    # Only add cards if supported
    if capability.maxCards > 0:
        user.cards.append(generateCard())

    # Only add fingerprints if supported
    if capability.maxFingerprints > 0:
        user.fingers.append(generateFinger())

    # Only add PIN if supported
    if capability.PINSupported:
        user.PIN = generatePIN()

    # Only add job codes if supported
    if capInfo.jobCodeSupported:
        user.jobCodes.append(generateJobCode())

    return user
```

### 5.2 Timestamp Generation

**Pattern**:

```python
from util import generateRandomDateTime
import datetime

# Generate timestamp in specific range
timestamp = generateRandomDateTime(
    minDateTime=datetime.datetime(2025, 1, 1),
    maxDateTime=datetime.datetime(2025, 12, 31)
)

# Convert to Unix timestamp
import time
unixTimestamp = int(time.mktime(timestamp.timetuple()))
```

### 5.3 Batch User Generation

**Pattern**:

```python
def generateRandomUsers(count, deviceCapability):
    users = []

    for i in range(count):
        user = user_pb2.UserInfo()
        user.hdr.ID = randomNumericUserID()
        user.name = generateName(includeKorean=True, length=16)

        if deviceCapability.maxCards > 0:
            cardData = generateCardID()
            card = user_pb2.CardData(index=0, data=cardData)
            user.cards.append(card)

        users.append(user)

    return users

# Usage
testUsers = generateRandomUsers(100, self.capability)
self.svcManager.enrollUsers(self.targetID, testUsers)
```

### 5.4 Avoiding Duplicates

**Pattern**:

```python
def generateUniqueUserIDs(count):
    generatedIDs = set()
    userIDs = []

    while len(userIDs) < count:
        newID = randomNumericUserID()
        if newID not in generatedIDs:
            generatedIDs.add(newID)
            userIDs.append(newID)

    return userIDs

# For card IDs
def generateUniqueCardIDs(count):
    generatedSerials = set()
    cards = []

    while len(cards) < count:
        serial = random.randint(1, 0xffffffff)
        if serial not in generatedSerials:
            generatedSerials.add(serial)
            cards.append(generateCardID(serial_number=serial))

    return cards
```

---

## Section 6: Data Validation Checklist

### 6.1 User Data Validation

**Before enrollment, verify**:

- [ ] User ID is unique (not already enrolled)
- [ ] User ID format matches device capability (alphanumeric vs numeric)
- [ ] User ID length <= 32 characters
- [ ] Name length <= 48 characters (or device-specific limit)
- [ ] PIN length is 4-16 digits if present
- [ ] Card count <= capability.maxCards
- [ ] Fingerprint count <= capability.maxFingerprints
- [ ] Face count <= capability.maxFaces
- [ ] Job codes only added if capInfo.jobCodeSupported
- [ ] Access group IDs exist on device

**After enrollment, verify**:

- [ ] User appears in getUsers() result
- [ ] All fields match original data
- [ ] User statistics updated correctly
- [ ] Events logged correctly

### 6.2 Config Data Validation

**Auth Config**:

- [ ] Auth mode supported by device (check extended\* fields in capability)
- [ ] Schedule ID exists (1 = always, or custom schedule ID)
- [ ] Auth mode appropriate for test (matches enrolled credential type)

**Door Config**:

- [ ] Door ID unique
- [ ] Entry device ID valid and registered
- [ ] Relay device ID and port valid
- [ ] Sensor device ID and port valid
- [ ] Timeout values reasonable (autoLockTimeout, heldOpenTimeout)

**Access Control**:

- [ ] Access group IDs unique
- [ ] Access level IDs unique
- [ ] Door IDs in access levels exist
- [ ] Schedule IDs in access levels exist
- [ ] Access groups assigned to users exist

### 6.3 Event Validation

**When verifying events**:

- [ ] Event monitoring enabled before action
- [ ] Timeout sufficient for event to occur (typically 3-5 seconds)
- [ ] Event code matches expected (use getEventDescription() to verify)
- [ ] Event fields match (deviceID, userID, cardData, etc.)
- [ ] Event timestamp reasonable
- [ ] Monitoring disabled after test to avoid interference

### 6.4 Cleanup Validation

**After test completion**:

- [ ] All test users removed
- [ ] All test configs restored to backup
- [ ] All test doors/access groups removed
- [ ] Device in same state as before test
- [ ] No orphaned data left on device
- [ ] Backup data successfully restored

---

## Section 7: Common Data Generation Scenarios

### 7.1 Generate User with Card Only

```python
def generateCardUser(deviceCapability):
    user = user_pb2.UserInfo()
    user.hdr.ID = randomNumericUserID()
    user.name = generateName(includeKorean=False, length=16)

    cardData = generateCardID()
    card = user_pb2.CardData(index=0, data=cardData)
    user.cards.append(card)

    return user
```

### 7.2 Generate User with Card + PIN

```python
def generateCardPinUser(deviceCapability, svcManager):
    user = generateCardUser(deviceCapability)

    if deviceCapability.PINSupported:
        pin = generateRandomPIN(lengthOfPin=8)
        user.PIN = svcManager.hashPIN(pin)

    return user
```

### 7.3 Generate User with Biometrics

```python
def generateBiometricUser(deviceID, deviceCapability, svcManager, useFinger=True, useFace=False):
    user = user_pb2.UserInfo()
    user.hdr.ID = randomNumericUserID()
    user.name = generateName(includeKorean=False, length=16)

    if useFinger and deviceCapability.maxFingerprints > 0:
        fingerData = svcManager.scanFingerprint(deviceID)
        finger = user_pb2.FingerData(index=0, templates=[fingerData])
        user.fingers.append(finger)

    if useFace and deviceCapability.maxFaces > 0:
        # Note: Face enrollment typically requires user ID to be already enrolled
        # So this might need two-step process
        pass

    return user
```

### 7.4 Generate User with Access Group

```python
def generateUserWithAccess(deviceID, accessGroupID, deviceCapability, svcManager):
    user = generateCardUser(deviceCapability)
    user.accessGroupIDs.append(accessGroupID)

    return user
```

### 7.5 Generate Complete Access Control Setup

```python
def setupAccessControl(deviceID, svcManager):
    # 1. Create schedule (if needed beyond ID=1 "always")
    schedule = schedule_pb2.Schedule()
    schedule.ID = 2
    schedule.name = "Business Hours"
    # ... configure weekly schedule
    svcManager.setSchedule(deviceID, schedule)

    # 2. Create door
    door = door_pb2.DoorInfo()
    door.doorID = 1
    door.name = "Main Door"
    door.entryDeviceID = deviceID
    # ... configure relay/sensor
    svcManager.setDoor(deviceID, door)

    # 3. Create access level
    accessLevel = access_pb2.AccessLevel()
    accessLevel.ID = 1
    accessLevel.name = "Employee Access"
    doorSchedule = access_pb2.DoorSchedule()
    doorSchedule.doorID = 1
    doorSchedule.scheduleID = 2
    accessLevel.doorSchedules.append(doorSchedule)
    svcManager.setAccessLevel(deviceID, accessLevel)

    # 4. Create access group
    accessGroup = access_pb2.AccessGroup()
    accessGroup.ID = 1
    accessGroup.name = "Employees"
    accessGroup.levelIDs.append(1)
    svcManager.setAccessGroup(deviceID, accessGroup)

    return {
        'scheduleID': 2,
        'doorID': 1,
        'levelID': 1,
        'groupID': 1
    }
```

---

## Section 8: Helper Functions from util.py

### 8.1 Schedule Helpers

```python
from util import onSchedule, onHoliday, onHolidayGroup
import time

# Check if current time is on schedule
currentTime = int(time.time())
isOnSchedule = onSchedule(schedule, holidayGroups, currentTime)

# Check if today is a holiday
isHoliday = onHoliday(holiday, currentTime)

# Check if today is in holiday group
isHolidayGroup = onHolidayGroup(holidayGroup, currentTime)
```

### 8.2 Device Type Helpers

```python
from util import kindOfStation
import device_pb2

# Check if device is station type (has keypad/display)
isStation = kindOfStation(device_pb2.BIOSTATION_3)  # Returns True
isStation = kindOfStation(device_pb2.XPASS_D2)      # Returns False
```

### 8.3 Card ID Helpers

```python
from util import getCardID

# Get serial number from card data
cardData = generateCardID(serial_number=123456)
serialNumber = getCardID(cardData, reverse=False)
# serialNumber = 123456

# Reverse byte order if needed
serialNumberReversed = getCardID(cardData, reverse=True)
```

---

## Section 9: Test Data File Management

### 9.1 Using Data Files

**Pattern from testCOMMONR.py**:

```python
# Get path to data file
dataPath = self.getDataFilePath('users.json', 'testdata')

# Load JSON data
import json
with open(dataPath, encoding='UTF-8') as f:
    testData = json.load(f)

# Load binary data (templates)
templatePath = self.getDataFilePath('finger.bin', 'fingerDB')
with open(templatePath, 'rb') as f:
    templateData = f.read()
```

### 9.2 Environment Variables

**Using BIOSTAR_AUTO_TEST_BASE_PATH**:

```python
import os

# Get base path from environment
basePath = os.environ.get("BIOSTAR_AUTO_TEST_BASE_PATH")
if basePath:
    configPath = os.path.join(basePath, "config.json")
else:
    configPath = os.path.join(os.getcwd(), "config.json")
```

### 9.3 Test Data Organization

**Recommended structure**:

```
test/
  ├── data/
  │   ├── users.json
  │   ├── doors.json
  │   └── access_groups.json
  ├── fingerDB/
  │   ├── finger1.bin
  │   └── finger2.bin
  ├── images/
  │   ├── photo1.jpg
  │   └── photo2.jpg
  └── environ.json
```

---

## Section 10: Integration with Workflow

**When to use this guide**:

- **Phase 3** of WORKFLOW_GUIDE: Test Data Preparation
- **After** device capability verification (Phase 4)
- **Before** test execution (Phase 6)

**How to combine with other guides**:

1. Analyze test requirements → Extract categories (WORKFLOW_GUIDE Section 1)
2. Find relevant resources → Use REFERENCE_GUIDE
3. Generate test data → Use THIS GUIDE
4. Execute test → Follow WORKFLOW_GUIDE Phase 6
5. Verify results → Use verification patterns from THIS GUIDE

**Example workflow integration**:

```python
def test_card_authentication(self):
    # Phase 4: Verify capability
    self.assertTrue(self.capability.maxCards > 0)

    # Phase 3: Generate data (THIS GUIDE)
    testUser = generateCardUser(self.capability)

    # Phase 5: Set auth mode
    self.setCardOnlyAuthMode(self.targetID, self.capability)

    # Phase 6: Execute test
    self.svcManager.enrollUsers(self.targetID, [testUser])

    # Phase 7: Verify (THIS GUIDE - Event verification)
    with EventMonitor(self.svcManager, self.targetID,
                      eventCode=0x1200, userID=testUser.hdr.ID) as monitor:
        # Perform authentication action
        self.assertTrue(monitor.caught(timeout=5.0))
```

---

**End of Test Data Generation Guide**
